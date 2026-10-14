"""
rate_limit.py — Giới hạn số câu hỏi mỗi phút theo (IP + user_id), lưu trong RAM.

Chỉ đúng khi chạy 1 worker uvicorn (trạng thái không chia sẻ giữa các process).
"""
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.core.auth import get_current_user_id
from app.core.config import settings

_WINDOW_SECONDS = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Sau Nginx: lấy IP gốc từ X-Forwarded-For (phần tử đầu tiên)
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request, user_id: str = Depends(get_current_user_id)) -> None:
    limit = settings.RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return
    now = time.monotonic()
    key = f"{_client_ip(request)}|{user_id}"
    q = _hits[key]
    while q and now - q[0] > _WINDOW_SECONDS:
        q.popleft()
    if len(q) >= limit:
        retry = int(_WINDOW_SECONDS - (now - q[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="Bạn hỏi quá nhanh, vui lòng thử lại sau ít phút.",
            headers={"Retry-After": str(retry)},
        )
    q.append(now)
    # Dọn key rỗng để dict không phình mãi
    if len(_hits) > 10_000:
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > _WINDOW_SECONDS]:
            del _hits[k]


def reset() -> None:
    _hits.clear()
