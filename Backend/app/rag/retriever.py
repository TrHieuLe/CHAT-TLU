import asyncio
import functools
import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from qdrant_client.http.models import Filter, FieldCondition, MatchValue, models

from app.core.config import settings
from app.core.timing import stage

try:
    from app.rag import embedder
except ImportError:
    embedder = None

logger = logging.getLogger(__name__)


# LRU cache embedding câu hỏi: câu hỏi lặp lại (kể cả khi semantic cache bị bỏ qua do có history)
# không phải encode lại BGE-M3 (~0.5s trên CPU)
_EMBED_CACHE_SIZE = 256
_embed_cache: "OrderedDict[str, tuple]" = OrderedDict()


def _embed_cache_get(key: str):
    hit = _embed_cache.get(key)
    if hit is not None:
        _embed_cache.move_to_end(key)
    return hit


def _embed_cache_put(key: str, value: tuple) -> None:
    _embed_cache[key] = value
    _embed_cache.move_to_end(key)
    while len(_embed_cache) > _EMBED_CACHE_SIZE:
        _embed_cache.popitem(last=False)


def clear_embed_cache() -> None:
    _embed_cache.clear()


def _to_list(x: Any):
    if x is None:
        return None
    if hasattr(x, "tolist"):
        return x.tolist()
    return x


class Retriever:
    def __init__(self, client, async_client=None):
        self.client = client
        self.async_client = async_client

    async def retrieve_v3(self, query: str, bot_id: int = 0):
        logger.info("Embedding query for retrieval...")

        current_embedder = embedder
        if current_embedder is None:
            from app.rag import embedder as current_embedder

        cache_key = " ".join((query or "").split()).lower()
        try:
            cached = _embed_cache_get(cache_key)
            if cached is not None:
                dense_, sparse_ = cached
            else:
                loop = asyncio.get_running_loop()
                embed_fn = functools.partial(
                    current_embedder.get_embeddings,
                    max_length=getattr(settings, "QUERY_MAX_LENGTH", 512),
                )
                with stage("embed"):
                    result = await loop.run_in_executor(None, embed_fn, [query])
                dense_, sparse_ = result
                if dense_ is not None and len(dense_) > 0:
                    _embed_cache_put(cache_key, (dense_, sparse_))
        except Exception as e:
            logger.exception("Embedding failed: %s", e)
            return []

        if dense_ is None or len(dense_) == 0:
            logger.warning("Dense embedding empty")
            return []

        dense_query = _to_list(dense_[0])
        if not dense_query or len(dense_query) == 0:
            logger.warning("Dense embedding invalid")
            return []

        sparse_query = sparse_[0] if (sparse_ is not None and len(sparse_) > 0) else None

        filter_obj = None
        if bot_id > 0:
            filter_obj = Filter(
                must=[FieldCondition(key="bot_id", match=MatchValue(value=bot_id))]
            )

        candidates_k = getattr(settings, "RETRIEVE_CANDIDATES_K", 12)
        top_k = getattr(settings, "TOP_K", 4)
        score_threshold = getattr(settings, "SCORE_THRESHOLD", None)
        collection_name = getattr(settings, "QDRANT_COLLECTION", None) or getattr(settings, "COLLECTION_NAME")

        raw_points = []
        try:
            if self.async_client:
                logger.info("Async hybrid retrieval (dense+sparse) - fetching %d candidates", candidates_k)

                prefetch = [
                    models.Prefetch(
                        query=dense_query,
                        using="dense",
                        limit=100,
                        filter=filter_obj,
                        score_threshold=score_threshold,
                    )
                ]

                if sparse_query:
                    prefetch.append(
                        models.Prefetch(
                            query=models.SparseVector(
                                indices=[int(k) for k in sparse_query.keys()],
                                values=[float(v) for v in sparse_query.values()],
                            ),
                            using="sparse",
                            limit=100,
                            filter=filter_obj,
                        )
                    )

                with stage("qdrant"):
                    result = await self.async_client.query_points(
                        collection_name=collection_name,
                        prefetch=prefetch,
                        query=models.FusionQuery(fusion=models.Fusion.RRF),
                        with_payload=True,
                        limit=candidates_k,
                        query_filter=filter_obj,
                    )
                raw_points = getattr(result, "points", []) or []

            else:
                logger.info("Sync dense retrieval (fallback) - fetching %d candidates", candidates_k)
                sync_client = getattr(self.client, "client", self.client)

                def _sync_query():
                    return sync_client.query_points(
                        collection_name=collection_name,
                        query=dense_query,
                        using="dense",
                        with_payload=True,
                        limit=candidates_k,
                        query_filter=filter_obj,
                        score_threshold=score_threshold,
                    )

                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, _sync_query)
                raw_points = getattr(result, "points", []) or []

        except Exception as e:
            logger.exception("Qdrant search failed: %s", e)
            return []

        if not raw_points:
            return []

        # Tầng Reranker (Cross-Encoder)
        try:
            from app.rag.reranker import get_reranker
            reranker = get_reranker()
            loop = asyncio.get_running_loop()
            with stage("rerank"):
                scored_candidates = await loop.run_in_executor(
                    None, reranker.rerank, query, raw_points, top_k
                )

            final_points = []
            for point, score in scored_candidates:
                if point.payload is not None and isinstance(point.payload, dict):
                    point.payload["rerank_score"] = round(score, 4)
                final_points.append(point)

            return final_points
        except Exception as e:
            logger.warning("Reranker failed, returning top Qdrant results: %s", e)
            return raw_points[:top_k]
