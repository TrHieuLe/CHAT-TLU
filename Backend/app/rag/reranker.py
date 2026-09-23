"""
reranker.py — Cross-Encoder / Reranker cho RAG pipeline.

Sử dụng mô hình Reranker (như BAAI/bge-reranker-base hoặc CrossEncoder) để đánh giá lại
mức độ liên quan ngữ nghĩa chi tiết giữa câu hỏi (query) và các đoạn văn bản (chunks)
được trả về từ bước Qdrant Hybrid Search.

Kiến trúc:
  [Qdrant Hybrid Search] ──(top 12-15)──▸ [Reranker] ──(top 3-4)──▸ [LLM Prompt]
"""

import logging
import math
from typing import Any, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

_reranker_instance = None


def _sigmoid(x: float) -> float:
    """Chuẩn hóa logit của reranker về khoảng [0.0, 1.0]."""
    try:
        if x > 30:
            return 1.0
        if x < -30:
            return 0.0
        return 1.0 / (1.0 + math.exp(-x))
    except Exception:
        return 0.5


class Reranker:
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.RERANKER_MODEL
        self._model = None
        self._load_failed = False

    def _load_model(self):
        if self._model is not None or self._load_failed:
            return self._model

        logger.info("⏳ Đang tải mô hình Reranker: %s ...", self.model_name)
        try:
            from FlagEmbedding import FlagReranker
            self._model = FlagReranker(self.model_name, use_fp16=False)
            logger.info("✅ FlagReranker đã tải thành công: %s", self.model_name)
            return self._model
        except Exception as e1:
            logger.warning("Không thể tải FlagReranker (%s), thử CrossEncoder: %s", self.model_name, e1)

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
            logger.info("✅ CrossEncoder đã tải thành công: %s", self.model_name)
            return self._model
        except Exception as e2:
            logger.error("Không thể tải Reranker model (%s): %s. Sẽ dùng fallback lexical rank.", self.model_name, e2)
            self._load_failed = True
            return None

    def rerank(
        self,
        query: str,
        chunks: List[Any],
        top_k: int = 4,
    ) -> List[Tuple[Any, float]]:
        """
        Đánh giá và sắp xếp lại danh sách chunks theo mức độ liên quan với query.

        Args:
            query: Câu hỏi của người dùng.
            chunks: Danh sách các chunk (có thể là đối tượng Point có payload hoặc chuỗi text).
            top_k: Số lượng chunk tối đa cần giữ lại sau khi rerank.

        Returns:
            Danh sách các tuple (chunk, normalized_score) được sắp xếp giảm dần theo điểm số.
        """
        if not chunks:
            return []

        if not settings.ENABLE_RERANKER:
            logger.debug("Reranker bị tắt bởi cấu hình ENABLE_RERANKER=False.")
            return [(c, 1.0) for c in chunks[:top_k]]

        # Trích xuất nội dung văn bản của từng chunk
        chunk_texts: List[str] = []
        for c in chunks:
            if hasattr(c, "payload") and isinstance(c.payload, dict):
                chunk_texts.append(c.payload.get("content", ""))
            elif isinstance(c, dict):
                chunk_texts.append(c.get("content", c.get("text", "")))
            elif isinstance(c, str):
                chunk_texts.append(c)
            else:
                chunk_texts.append(str(c))

        model = self._load_model()

        if model is not None:
            try:
                pairs = [[query, text] for text in chunk_texts]
                scores = model.compute_score(pairs)

                if isinstance(scores, (int, float)):
                    scores = [scores]

                scored_chunks = []
                for chunk, raw_score in zip(chunks, scores):
                    norm_score = _sigmoid(float(raw_score))
                    scored_chunks.append((chunk, norm_score))

                scored_chunks.sort(key=lambda x: x[1], reverse=True)
                logger.info(
                    "Đã rerank %d chunks -> chọn top %d (điểm cao nhất: %.3f, thấp nhất: %.3f)",
                    len(chunks),
                    min(top_k, len(scored_chunks)),
                    scored_chunks[0][1] if scored_chunks else 0.0,
                    scored_chunks[-1][1] if scored_chunks else 0.0,
                )
                return scored_chunks[:top_k]
            except Exception as e:
                logger.exception("Lỗi khi chạy model rerank, chuyển sang fallback: %s", e)

        # Fallback khi model không khả dụng: xếp hạng dựa trên mật độ từ khóa (Lexical Jaccard/Overlap)
        scored_chunks = []
        q_tokens = set(query.lower().split())
        for idx, (chunk, text) in enumerate(zip(chunks, chunk_texts)):
            t_tokens = set(text.lower().split())
            overlap = len(q_tokens & t_tokens)
            base_score = overlap / max(len(q_tokens), 1)
            pos_bonus = 1.0 / (idx + 1) * 0.1
            score = min(1.0, base_score + pos_bonus)
            scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]


def get_reranker() -> Reranker:
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance
