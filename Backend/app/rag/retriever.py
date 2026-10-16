import asyncio
import functools
import logging
import re
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


# Header chunk do chunk_doc dựng: "Tài liệu > Mục > 6. Ngành Công nghệ thông tin." (bản ghi đánh số của file .txt)
_RECORD_HEADER_RE = re.compile(r" > \d+\. [^>]*$")
_SUMMARY_HEADER_RE = re.compile(r" > TỔNG HỢP\b")
_ROLLUP_MIN_RECORDS = 3
_ROLLUP_MAX_SUMMARIES = 2


def _first_line(point) -> str:
    payload = getattr(point, "payload", None) or {}
    return (payload.get("content") or "").split("\n", 1)[0]


def _is_record(point) -> bool:
    return bool(_RECORD_HEADER_RE.search(_first_line(point)))


def _rollup_doc(points: list) -> str | None:
    """Tên tài liệu nếu ít nhất _ROLLUP_MIN_RECORDS chunk là bản ghi đánh số của cùng tài liệu đó."""
    counts: dict[str, int] = {}
    for p in points:
        if _is_record(p):
            doc = (p.payload or {}).get("doc_name", "")
            counts[doc] = counts.get(doc, 0) + 1
    doc, n = max(counts.items(), key=lambda kv: kv[1], default=("", 0))
    return doc if doc and n >= _ROLLUP_MIN_RECORDS else None


def merge_rollup(points: list, summaries: list, top_k: int) -> list:
    """Giữ bản ghi khớp nhất, chèn các mục tổng hợp ngay sau, rồi lấp phần còn lại theo thứ tự cũ."""
    seen = {str(p.id) for p in points}
    extra = [s for s in summaries if str(s.id) not in seen][:_ROLLUP_MAX_SUMMARIES]
    if not extra:
        return points[:top_k]
    return (points[:1] + extra + points[1:])[:top_k]


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

    async def embed_query(self, query: str):
        """
        Embed câu hỏi (dense, sparse) qua LRU cache. Dùng chung cho retrieval và semantic cache
        để mỗi câu hỏi chỉ phải encode BGE-M3 một lần.
        """
        current_embedder = embedder
        if current_embedder is None:
            from app.rag import embedder as current_embedder

        cache_key = " ".join((query or "").split()).lower()
        cached = _embed_cache_get(cache_key)
        if cached is not None:
            return cached
        loop = asyncio.get_running_loop()
        embed_fn = functools.partial(
            current_embedder.get_embeddings,
            max_length=getattr(settings, "QUERY_MAX_LENGTH", 512),
        )
        with stage("embed"):
            dense_, sparse_ = await loop.run_in_executor(None, embed_fn, [query])
        if dense_ is not None and len(dense_) > 0:
            _embed_cache_put(cache_key, (dense_, sparse_))
        return dense_, sparse_

    async def retrieve_v3(self, query: str, bot_id: int = 0):
        logger.info("Embedding query for retrieval...")

        try:
            dense_, sparse_ = await self.embed_query(query)
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
        except Exception as e:
            logger.warning("Reranker failed, returning top Qdrant results: %s", e)
            final_points = raw_points[:top_k]

        return await self._rollup(final_points, top_k, collection_name)

    async def _rollup(self, points: list, top_k: int, collection_name: str) -> list:
        """
        Câu hỏi bao quát cả danh sách ("điểm chuẩn của trường", "chỉ tiêu tất cả các ngành") khớp đều với mọi
        bản ghi nên top-k toàn bản ghi lẻ của một tài liệu. Khi đó thêm các mục "TỔNG HỢP ..." của tài liệu
        đó (chunk bao quát cả danh sách), giữ bản ghi khớp nhất. Câu hỏi về một ngành vẫn có bản ghi đó đứng đầu.
        """
        doc = _rollup_doc(points)
        if not doc or not self.async_client:
            return points
        try:
            summaries, _ = await self.async_client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(must=[FieldCondition(key="doc_name", match=MatchValue(value=doc))]),
                limit=256,
                with_payload=True,
            )
        except Exception as e:
            logger.warning("Rollup lookup failed for %s: %s", doc, e)
            return points
        summaries = [s for s in summaries if _SUMMARY_HEADER_RE.search(_first_line(s))]
        # mục tổng hợp ngắn hơn (vd cao nhất/thấp nhất) xếp sau mục liệt kê đầy đủ
        summaries.sort(key=lambda s: -len((s.payload or {}).get("content", "")))
        return merge_rollup(points, summaries, top_k)
