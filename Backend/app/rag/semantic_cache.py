"""
semantic_cache.py — Bộ nhớ đệm ngữ nghĩa (Semantic Cache) cho StudyBot TLU.

Câu hỏi độc lập (lượt đầu, không cá nhân hóa) được trả lời lại từ cache nếu:
  1. exact     — trùng chuỗi sau khi chuẩn hóa hoa/thường/khoảng trắng
  2. canonical — trùng chuỗi "từ nội dung": bỏ từ đệm (cho em hỏi, ạ, hãy, đi...),
                 mở rộng viết tắt (ktx → ký túc xá), giữ nguyên thứ tự
  3. semantic  — cosine BGE-M3 >= ngưỡng VÀ cùng TẬP từ nội dung (khác thứ tự)

Vì sao không dùng riêng cosine: đo bằng scripts/eval_cache_threshold.py, BGE-M3 cho
"học lực giỏi cần CPA bao nhiêu" vs "...khá..." sim = 0.972, trong khi các câu cùng ý
viết khác có thể chỉ ~0.78 → không ngưỡng nào vừa an toàn vừa hữu ích. Đòi hỏi cùng
từ nội dung đảm bảo không trả lời nhầm câu khác ý (giỏi/khá, học lại/thi lại, kỳ 1/kỳ 2).

Dữ liệu nằm trong RAM (ma trận numpy để so khớp nhanh) và được ghi xuống SQLite
(nếu có persist_path) để không mất khi khởi động lại. Mỗi entry có TTL; toàn bộ
cache bị xóa khi kho tài liệu thay đổi (xem invalidate_semantic_cache).
"""
import json
import logging
import re
import sqlite3
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.90
MAX_CACHE_SIZE = 300
DEFAULT_TTL_SECONDS = 7 * 24 * 3600

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|\w+", re.UNICODE)

# Từ đệm / xưng hô không đổi nghĩa câu hỏi. CỐ Ý giữ lại từ để hỏi (nào, đâu, bao nhiêu,
# khi, sao) và phủ định (không, chưa) vì chúng đổi nghĩa ("đăng ký ktx khi nào" ≠ "ở đâu").
_FILLER_WORDS = {
    "cho", "em", "mình", "tôi", "tớ", "con", "bạn", "ad", "admin", "hỏi", "hãy", "ạ", "ơi", "với",
    "nhé", "nha", "nhỉ", "vậy", "đi", "giúp", "xin", "ơn", "vui", "lòng", "là", "thì", "được",
    "để", "của", "các", "những", "và", "cái", "về", "biết", "muốn", "gì", "ạ", "dạ", "vâng",
}
# Các cách hỏi "như thế nào" tương đương → một token chung
_HOW_PHRASES = re.compile(r"\b(?:như\s+thế\s+nào|thế\s+nào|ra\s+sao|như\s+nào)\b")


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
    canonical: str = ""
    title: str = ""  # tiêu đề phiên do AI sinh — dùng lại khi trúng cache để khỏi gọi Gemini

    def __post_init__(self):
        if not self.canonical:
            self.canonical = canonical_key(self.query)


def _normalize_str(text: str) -> str:
    """Chuẩn hóa chuỗi văn bản phục vụ so khớp trực tiếp."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).lower().strip()
    return " ".join(text.split())


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER_RE.findall(text or "")}


def numbers_compatible(q1: str, q2: str) -> bool:
    """Hai câu hỏi chỉ được coi là tương đương khi tập các con số trong câu giống nhau."""
    return _numbers(q1) == _numbers(q2)


def content_tokens(text: str) -> list[str]:
    """Các từ mang nội dung của câu hỏi (đã mở rộng viết tắt, bỏ từ đệm), giữ thứ tự."""
    if not text:
        return []
    try:
        from app.rag.query_enhancer import normalize_abbreviations_only
        text = normalize_abbreviations_only(text)
    except Exception:
        pass
    text = unicodedata.normalize("NFC", text).lower()
    text = _HOW_PHRASES.sub(" thế_nào ", text)
    return [t.replace(",", ".") for t in _TOKEN_RE.findall(text) if t not in _FILLER_WORDS]


def canonical_key(text: str) -> str:
    return " ".join(content_tokens(text))


def _unit(v) -> Optional[np.ndarray]:
    if v is None:
        return None
    arr = np.asarray(v, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm == 0 or not np.isfinite(norm):
        return None
    return arr / norm


def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Tính cosine similarity giữa 2 vectors."""
    a, b = _unit(v1), _unit(v2)
    if a is None or b is None or a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b))


class SemanticCache:
    """
    Semantic Cache với Exact Match & Vector Cosine Similarity, TTL và lưu trữ SQLite tùy chọn.
    """
    def __init__(
        self,
        max_size: int = MAX_CACHE_SIZE,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        ttl_seconds: Optional[float] = DEFAULT_TTL_SECONDS,
        persist_path: Optional[str] = None,
    ):
        self.max_size = max_size
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self._exact_map: dict[str, CacheEntry] = {}
        self._canonical_map: dict[str, CacheEntry] = {}
        self._entries: list[CacheEntry] = []
        self._matrix: Optional[np.ndarray] = None   # (n_vec, dim) — vector đã chuẩn hóa
        self._matrix_entries: list[CacheEntry] = []
        self._lock = threading.RLock()
        self._total_lookups = 0
        self._cache_hits = 0
        self._semantic_hits = 0
        self._db: Optional[sqlite3.Connection] = None
        if persist_path:
            self._open_db(persist_path)

    # ─── Persistence ─────────────────────────────────────────────────────────

    def _open_db(self, path: str) -> None:
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS semantic_cache ("
                " normalized_query TEXT PRIMARY KEY, query TEXT, answer TEXT, sources TEXT,"
                " vector BLOB, created_at REAL, last_accessed REAL, hits INTEGER)"
            )
            self._db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            cols = {r[1] for r in self._db.execute("PRAGMA table_info(semantic_cache)")}
            if "title" not in cols:
                self._db.execute("ALTER TABLE semantic_cache ADD COLUMN title TEXT DEFAULT ''")
            self._db.commit()
            self._load_from_db()
        except Exception as e:
            logger.warning("[SemanticCache] Không mở được SQLite %s, chỉ dùng RAM: %s", path, e)
            self._db = None

    def _load_from_db(self) -> None:
        rows = self._db.execute(
            "SELECT normalized_query, query, answer, sources, vector, created_at, last_accessed, hits, title"
            " FROM semantic_cache ORDER BY last_accessed DESC LIMIT ?", (self.max_size,)
        ).fetchall()
        now = time.time()
        for norm_q, query, answer, sources, blob, created, accessed, hits, title in rows:
            if self.ttl_seconds and now - created > self.ttl_seconds:
                continue
            vec = np.frombuffer(blob, dtype=np.float32).copy() if blob else None
            entry = CacheEntry(query=query, normalized_query=norm_q, answer=answer,
                               source_names=json.loads(sources or "[]"), vector=vec,
                               created_at=created, last_accessed=accessed, hits=hits or 0,
                               title=title or "")
            self._exact_map[norm_q] = entry
            self._index_canonical(entry)
            self._entries.append(entry)
        self._rebuild_matrix()
        if self._entries:
            logger.info("[SemanticCache] Đã nạp %d entry từ SQLite", len(self._entries))

    def _db_write(self, entry: CacheEntry) -> None:
        if self._db is None:
            return
        try:
            blob = entry.vector.astype(np.float32).tobytes() if entry.vector is not None else None
            self._db.execute(
                "INSERT OR REPLACE INTO semantic_cache"
                " (normalized_query, query, answer, sources, vector, created_at, last_accessed, hits, title)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (entry.normalized_query, entry.query, entry.answer, json.dumps(entry.source_names, ensure_ascii=False),
                 blob, entry.created_at, entry.last_accessed, entry.hits, entry.title),
            )
            self._db.commit()
        except Exception as e:
            logger.warning("[SemanticCache] Ghi SQLite thất bại: %s", e)

    def _db_delete(self, normalized_query: Optional[str] = None) -> None:
        if self._db is None:
            return
        try:
            if normalized_query is None:
                self._db.execute("DELETE FROM semantic_cache")
            else:
                self._db.execute("DELETE FROM semantic_cache WHERE normalized_query = ?", (normalized_query,))
            self._db.commit()
        except Exception as e:
            logger.warning("[SemanticCache] Xóa SQLite thất bại: %s", e)

    def get_meta(self, key: str) -> Optional[str]:
        if self._db is None:
            return getattr(self, "_meta", {}).get(key)
        row = self._db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        if self._db is None:
            self._meta = {**getattr(self, "_meta", {}), key: value}
            return
        self._db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self._db.commit()

    # ─── Internals ───────────────────────────────────────────────────────────

    def _rebuild_matrix(self) -> None:
        with_vec = [e for e in self._entries if e.vector is not None]
        if not with_vec:
            self._matrix, self._matrix_entries = None, []
            return
        dim = with_vec[0].vector.shape[0]
        with_vec = [e for e in with_vec if e.vector.shape[0] == dim]
        self._matrix = np.stack([e.vector for e in with_vec]).astype(np.float32)
        self._matrix_entries = with_vec

    def _index_canonical(self, entry: CacheEntry) -> None:
        if entry.canonical:
            self._canonical_map[entry.canonical] = entry

    def _expired(self, entry: CacheEntry) -> bool:
        return bool(self.ttl_seconds) and (time.time() - entry.created_at) > self.ttl_seconds

    def _remove(self, entry: CacheEntry) -> None:
        self._exact_map.pop(entry.normalized_query, None)
        if self._canonical_map.get(entry.canonical) is entry:
            self._canonical_map.pop(entry.canonical, None)
        try:
            self._entries.remove(entry)
        except ValueError:
            pass
        self._db_delete(entry.normalized_query)
        self._rebuild_matrix()

    def _touch(self, entry: CacheEntry) -> None:
        entry.hits += 1
        entry.last_accessed = time.time()
        self._cache_hits += 1
        self._db_write(entry)

    # ─── Public API ──────────────────────────────────────────────────────────

    def get(self, query: str, query_vector: Optional[np.ndarray] = None) -> Optional[Tuple[str, List[str], str]]:
        """
        Tìm câu trả lời trong cache.

        Returns:
            (answer, source_names, match_type) với match_type 'exact' | 'canonical' | 'semantic'; None nếu miss.
        """
        found = self.get_entry(query, query_vector)
        if found is None:
            return None
        entry, match_type = found
        return entry.answer, entry.source_names, match_type

    def get_entry(self, query: str, query_vector: Optional[np.ndarray] = None) -> Optional[Tuple[CacheEntry, str]]:
        """Như get() nhưng trả về (CacheEntry, match_type) để lấy thêm metadata (vd title)."""
        with self._lock:
            self._total_lookups += 1
            norm_q = _normalize_str(query)
            if not norm_q:
                return None

            # 1. Exact match
            entry = self._exact_map.get(norm_q)
            if entry is not None:
                if self._expired(entry):
                    self._remove(entry)
                else:
                    self._touch(entry)
                    logger.info("⚡ [SemanticCache] EXACT HIT: '%s' (hits: %d)", query[:50], entry.hits)
                    return entry, "exact"

            # 2. Canonical match (cùng từ nội dung, cùng thứ tự)
            q_tokens = content_tokens(query)
            canon = " ".join(q_tokens)
            entry = self._canonical_map.get(canon) if canon else None
            if entry is not None and not self._expired(entry):
                self._touch(entry)
                logger.info("⚡ [SemanticCache] CANONICAL HIT: '%s' -> '%s'", query[:50], entry.query[:50])
                return entry, "canonical"

            # 3. Semantic match (cosine cao + cùng tập từ nội dung)
            qv = _unit(query_vector)
            if qv is None or self._matrix is None or qv.shape[0] != self._matrix.shape[1]:
                return None
            q_token_set = set(q_tokens)

            sims = self._matrix @ qv
            for idx in np.argsort(-sims):
                score = float(sims[idx])
                if score < self.similarity_threshold:
                    break
                cand = self._matrix_entries[idx]
                if self._expired(cand):
                    continue
                if not numbers_compatible(query, cand.query) or set(cand.canonical.split()) != q_token_set:
                    logger.info("[SemanticCache] Bỏ qua (khác từ nội dung, sim=%.3f): '%s' vs '%s'",
                                score, query[:40], cand.query[:40])
                    continue
                self._touch(cand)
                self._semantic_hits += 1
                logger.info("⚡ [SemanticCache] SEMANTIC HIT (sim=%.3f): '%s' -> '%s'",
                            score, query[:50], cand.query[:50])
                return cand, "semantic"
            return None

    def put(
        self,
        query: str,
        answer: str,
        source_names: Optional[List[str]] = None,
        query_vector: Optional[np.ndarray] = None,
        title: str = "",
    ) -> None:
        """Lưu một câu hỏi và câu trả lời vào cache."""
        norm_q = _normalize_str(query)
        if not norm_q or not answer or len(answer.strip()) < 10:
            return
        vec = _unit(query_vector)

        with self._lock:
            existing = self._exact_map.get(norm_q)
            if existing is not None:
                existing.answer = answer
                existing.source_names = source_names or []
                existing.title = title or existing.title
                if vec is not None:
                    existing.vector = vec
                existing.created_at = existing.last_accessed = time.time()
                self._index_canonical(existing)
                self._db_write(existing)
                self._rebuild_matrix()
                return

            if len(self._entries) >= self.max_size:
                # Loại entry ít được dùng nhất (ít hit, lâu chưa truy cập)
                victim = min(self._entries, key=lambda e: (e.hits, e.last_accessed))
                self._remove(victim)

            entry = CacheEntry(query=query, normalized_query=norm_q, answer=answer,
                               source_names=source_names or [], vector=vec, title=title or "")
            self._exact_map[norm_q] = entry
            self._index_canonical(entry)
            self._entries.append(entry)
            self._db_write(entry)
            self._rebuild_matrix()
            logger.debug("[SemanticCache] Added '%s'. Total: %d", norm_q[:40], len(self._entries))

    def clear(self) -> None:
        """Xóa toàn bộ cache (RAM + SQLite)."""
        with self._lock:
            self._exact_map.clear()
            self._canonical_map.clear()
            self._entries.clear()
            self._matrix, self._matrix_entries = None, []
            self._total_lookups = 0
            self._cache_hits = 0
            self._semantic_hits = 0
            self._db_delete()

    def get_stats(self) -> dict:
        """Lấy số liệu thống kê hiệu năng của Cache."""
        hit_rate = (self._cache_hits / self._total_lookups * 100) if self._total_lookups > 0 else 0.0
        return {
            "cached_entries": len(self._entries),
            "total_lookups": self._total_lookups,
            "cache_hits": self._cache_hits,
            "semantic_hits": self._semantic_hits,
            "hit_rate_pct": round(hit_rate, 2),
            "similarity_threshold": self.similarity_threshold,
            "persistent": self._db is not None,
        }


# Singleton instance
_semantic_cache_instance: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """Singleton getter cho SemanticCache (cấu hình từ settings)."""
    global _semantic_cache_instance
    if _semantic_cache_instance is None:
        from app.core.config import settings
        _semantic_cache_instance = SemanticCache(
            max_size=settings.SEMANTIC_CACHE_MAX_SIZE,
            similarity_threshold=settings.SEMANTIC_CACHE_THRESHOLD,
            ttl_seconds=settings.SEMANTIC_CACHE_TTL_SECONDS,
            persist_path=settings.SEMANTIC_CACHE_DB or None,
        )
    return _semantic_cache_instance


def invalidate_semantic_cache(reason: str = "") -> None:
    """Xóa cache khi kho tài liệu thay đổi (upload / xóa / crawl) để không trả lời theo dữ liệu cũ."""
    try:
        get_semantic_cache().clear()
        logger.info("[SemanticCache] Đã xóa cache: %s", reason or "kho tài liệu thay đổi")
    except Exception as e:
        logger.warning("[SemanticCache] Không thể xóa cache: %s", e)


async def check_kb_fingerprint(async_client, collection_name: str) -> bool:
    """
    So số điểm trong collection Qdrant với giá trị đã lưu cùng cache. Khác nhau → kho tài liệu
    đã đổi ngoài tiến trình này (vd chạy ingest.py từ CLI) → xóa cache. Trả về True nếu đã xóa.
    """
    info = await async_client.get_collection(collection_name)
    current = str(getattr(info, "points_count", None))
    cache = get_semantic_cache()
    previous = cache.get_meta("kb_points_count")
    if previous != current:
        if previous is not None:
            invalidate_semantic_cache(f"số điểm Qdrant đổi {previous} → {current}")
        cache.set_meta("kb_points_count", current)
        return previous is not None
    return False


async def watch_kb_changes(async_client, collection_name: str, interval_seconds: float = 60.0) -> None:
    """Chạy nền: định kỳ kiểm tra kho tài liệu thay đổi để xóa semantic cache."""
    import asyncio
    while True:
        try:
            await check_kb_fingerprint(async_client, collection_name)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("[SemanticCache] Kiểm tra kho tài liệu thất bại: %s", e)
        await asyncio.sleep(interval_seconds)
