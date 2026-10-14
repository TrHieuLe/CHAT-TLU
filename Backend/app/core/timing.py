"""
timing.py — Đo thời gian từng bước xử lý một câu hỏi (cache, embed, qdrant, rerank, LLM...).

Mỗi request tạo một StageTimer; timer hiện tại được gắn vào contextvar để các tầng
bên dưới (retriever, llm_service) ghi thêm bước mà không cần truyền tham số.
Kết quả được log ra và lưu vào ring buffer để xem p50/p95 qua /api/chat/perf/stats.
"""
import logging
import time
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_RECORDS = 500
_records: deque[dict] = deque(maxlen=_MAX_RECORDS)
_current: ContextVar[Optional["StageTimer"]] = ContextVar("stage_timer", default=None)


class StageTimer:
    def __init__(self, label: str = "chat"):
        self.label = label
        self.start = time.perf_counter()
        self.stages: dict[str, float] = {}
        self.tags: dict[str, str] = {}
        self._token = _current.set(self)

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self.start) * 1000

    def mark(self, name: str, ms: float) -> None:
        self.stages[name] = round(self.stages.get(name, 0.0) + ms, 1)

    def mark_since_start(self, name: str) -> None:
        """Ghi mốc thời gian tính từ lúc bắt đầu request (vd: ttft)."""
        if name not in self.stages:
            self.stages[name] = round(self.elapsed_ms(), 1)

    @contextmanager
    def stage(self, name: str):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.mark(name, (time.perf_counter() - t0) * 1000)

    def finish(self) -> dict:
        total = round(self.elapsed_ms(), 1)
        record = {"label": self.label, "total": total, **self.stages, **self.tags}
        _records.append(record)
        try:
            _current.reset(self._token)
        except ValueError:
            # Generator có thể kết thúc ở context khác (StreamingResponse)
            _current.set(None)
        parts = " ".join(f"{k}={v}" for k, v in self.stages.items())
        tags = " ".join(f"{k}={v}" for k, v in self.tags.items())
        logger.info("⏱ [%s] total=%.1fms %s %s", self.label, total, parts, tags)
        return record


def current_timer() -> Optional[StageTimer]:
    return _current.get()


@contextmanager
def stage(name: str):
    """Đo một bước nếu đang có timer của request; không có thì bỏ qua."""
    timer = _current.get()
    if timer is None:
        yield
        return
    with timer.stage(name):
        yield


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


def get_stats(label: Optional[str] = None) -> dict:
    rows = [r for r in _records if label is None or r.get("label") == label]
    keys: set[str] = set()
    for r in rows:
        keys.update(k for k, v in r.items() if isinstance(v, (int, float)))
    stats = {}
    for k in sorted(keys):
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        stats[k] = {
            "count": len(vals),
            "p50": round(_percentile(vals, 50), 1),
            "p95": round(_percentile(vals, 95), 1),
            "max": round(max(vals), 1),
        }
    return {"requests": len(rows), "stages_ms": stats, "recent": list(rows)[-10:]}


def clear_stats() -> None:
    _records.clear()
