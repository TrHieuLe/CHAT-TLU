"""
semantic_cache.py — Bộ nhớ đệm ngữ nghĩa (Semantic Cache) cho StudyBot TLU.
Giúp phản hồi các câu hỏi phổ biến hoặc tương đương ngữ nghĩa trong vòng < 30ms,
giảm thiểu độ trễ, tiết kiệm quota API Gemini và tối ưu tài nguyên hệ thống.
"""
import time
import logging
import unicodedata
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.94
MAX_CACHE_SIZE = 300


@dataclass
class CacheEntry:
    query: str
    normalized_query: str
    answer: str
    source_names: List[str]
    vector: Optional[np.ndarray] = None
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    hits: int = 0


def _normalize_str(text: str) -> str:
    """Chuẩn hóa chuỗi văn bản phục vụ so khớp trực tiếp."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).lower().strip()
    return " ".join(text.split())


def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Tính cosine similarity giữa 2 vectors."""
    try:
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))
    except Exception:
        return 0.0


class SemanticCache:
    """
    In-memory Semantic Cache với hỗ trợ Exact Match & Vector Cosine Similarity.
    """
    def __init__(self, max_size: int = MAX_CACHE_SIZE, similarity_threshold: float = SIMILARITY_THRESHOLD):
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self._exact_map: dict[str, CacheEntry] = {}
        self._entries: list[CacheEntry] = []
        self._total_lookups = 0
        self._cache_hits = 0

    def get(self, query: str, query_vector: Optional[np.ndarray] = None) -> Optional[Tuple[str, List[str], str]]:
        """
        Tìm kiếm câu trả lời trong cache:
        1. Exact match qua normalized query (0ms).
        2. Semantic match qua cosine similarity với các cached vectors (< 5ms).

        Returns:
            Tuple (answer, source_names, match_type) hoặc None nếu cache miss.
            match_type có thể là 'exact' hoặc 'semantic'.
        """
        self._total_lookups += 1
        norm_q = _normalize_str(query)
        if not norm_q:
            return None

        # 1. Exact match
        if norm_q in self._exact_map:
            entry = self._exact_map[norm_q]
            entry.hits += 1
            entry.last_accessed = time.time()
            self._cache_hits += 1
            logger.info("⚡ [SemanticCache] EXACT HIT cho câu hỏi: '%s' (hits: %d)", query[:50], entry.hits)
            return entry.answer, entry.source_names, "exact"

        # 2. Semantic vector match
        if query_vector is not None and self._entries:
            best_score = -1.0
            best_entry: Optional[CacheEntry] = None

            for entry in self._entries:
                if entry.vector is not None:
                    sim = _cosine_similarity(query_vector, entry.vector)
                    if sim > best_score:
                        best_score = sim
                        best_entry = entry

            if best_entry and best_score >= self.similarity_threshold:
                best_entry.hits += 1
                best_entry.last_accessed = time.time()
                self._cache_hits += 1
                logger.info(
                    "⚡ [SemanticCache] SEMANTIC HIT (sim=%.3f >= %.2f) cho câu hỏi: '%s' -> gốc: '%s'",
                    best_score, self.similarity_threshold, query[:50], best_entry.query[:50]
                )
                return best_entry.answer, best_entry.source_names, "semantic"

        return None

    def put(
        self,
        query: str,
        answer: str,
        source_names: Optional[List[str]] = None,
        query_vector: Optional[np.ndarray] = None,
    ) -> None:
        """
        Lưu một câu hỏi và câu trả lời vào cache.
        """
        norm_q = _normalize_str(query)
        if not norm_q or not answer or len(answer.strip()) < 10:
            return

        # Nếu đã có trong exact map, chỉ cập nhật
        if norm_q in self._exact_map:
            existing = self._exact_map[norm_q]
            existing.answer = answer
            existing.source_names = source_names or []
            if query_vector is not None:
                existing.vector = query_vector
            existing.last_accessed = time.time()
            return

        # Kiểm tra giới hạn dung lượng để LRU eviction
        if len(self._entries) >= self.max_size:
            # Xóa entry ít được truy cập nhất
            self._entries.sort(key=lambda e: (e.hits, e.last_accessed))
            oldest = self._entries.pop(0)
            self._exact_map.pop(oldest.normalized_query, None)

        entry = CacheEntry(
            query=query,
            normalized_query=norm_q,
            answer=answer,
            source_names=source_names or [],
            vector=query_vector,
        )

        self._exact_map[norm_q] = entry
        self._entries.append(entry)
        logger.debug("[SemanticCache] Added entry for '%s'. Total: %d", norm_q[:40], len(self._entries))

    def clear(self) -> None:
        """Xóa toàn bộ cache."""
        self._exact_map.clear()
        self._entries.clear()
        self._total_lookups = 0
        self._cache_hits = 0

    def get_stats(self) -> dict:
        """Lấy số liệu thống kê hiệu năng của Cache."""
        hit_rate = (self._cache_hits / self._total_lookups * 100) if self._total_lookups > 0 else 0.0
        return {
            "cached_entries": len(self._entries),
            "total_lookups": self._total_lookups,
            "cache_hits": self._cache_hits,
            "hit_rate_pct": round(hit_rate, 2),
        }


# Singleton instance
_semantic_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Singleton getter cho SemanticCache."""
    global _semantic_cache_instance
    if _semantic_cache_instance is None:
        _semantic_cache_instance = SemanticCache()
    return _semantic_cache_instance
