"""
admin.py — API quản trị: xem và khai thác phản hồi (like/dislike) của người dùng.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_admin
from app.core.config import settings
from app.models.database import ChatMessage, ChatMessageFeedback, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _eval_path() -> Path:
    p = Path(settings.EVAL_CANDIDATES_PATH)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


def iso_utc(dt: datetime | None) -> str | None:
    """SQLite trả datetime không kèm múi giờ (thực chất là UTC) → gắn UTC để frontend đổi đúng giờ."""
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def _sources(meta: str | None) -> list:
    try:
        return json.loads(meta or "{}").get("sources", [])
    except (ValueError, AttributeError):
        return []


async def _question_before(db: AsyncSession, answer: ChatMessage) -> str | None:
    """Câu hỏi của người dùng ngay trước câu trả lời trong cùng phiên."""
    res = await db.execute(
        select(ChatMessage.content)
        .where(
            ChatMessage.session_id == answer.session_id,
            ChatMessage.role == "user",
            ChatMessage.id < answer.id,
        )
        .order_by(ChatMessage.id.desc())
        .limit(1)
    )
    return res.scalar_one_or_none()


@router.get("/feedback/summary")
async def feedback_summary(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Số like/dislike theo ngày trong `days` ngày gần nhất."""
    days = min(max(days, 1), 365)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = func.date(ChatMessageFeedback.created_at)
    res = await db.execute(
        select(day, ChatMessageFeedback.rating, func.count())
        .where(ChatMessageFeedback.created_at >= since)
        .group_by(day, ChatMessageFeedback.rating)
        .order_by(day)
    )
    by_day: dict[str, dict[str, int]] = {}
    totals = {"like": 0, "dislike": 0}
    for d, rating, n in res.all():
        row = by_day.setdefault(str(d), {"like": 0, "dislike": 0})
        if rating in row:
            row[rating] += n
            totals[rating] += n
    return {
        "days": days,
        "totals": totals,
        "by_day": [{"date": d, **v} for d, v in sorted(by_day.items())],
    }


@router.get("/feedback")
async def list_feedback(
    rating: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Danh sách phản hồi mới nhất kèm câu hỏi, câu trả lời và nguồn."""
    q = select(ChatMessageFeedback, ChatMessage).outerjoin(
        ChatMessage, ChatMessage.id == ChatMessageFeedback.message_id
    )
    count_q = select(func.count()).select_from(ChatMessageFeedback)
    if rating in {"like", "dislike"}:
        q = q.where(ChatMessageFeedback.rating == rating)
        count_q = count_q.where(ChatMessageFeedback.rating == rating)
    q = q.order_by(ChatMessageFeedback.created_at.desc()).limit(min(max(limit, 1), 200)).offset(max(offset, 0))

    total = (await db.execute(count_q)).scalar_one()
    items = []
    for fb, msg in (await db.execute(q)).all():
        items.append({
            "id": fb.id,
            "rating": fb.rating,
            "comment": fb.comment,
            "created_at": iso_utc(fb.created_at),
            "session_id": fb.session_id,
            "message_id": fb.message_id,
            "question": await _question_before(db, msg) if msg else None,
            "answer": msg.content if msg else None,
            "sources": _sources(msg.source_docs) if msg else [],
        })
    return {"total": total, "items": items}


@router.post("/feedback/{feedback_id}/to-eval")
async def add_feedback_to_eval(feedback_id: int, db: AsyncSession = Depends(get_db)):
    """
    Ghi câu hỏi của phản hồi vào file JSONL ứng viên cho bộ đánh giá.
    Người quản trị bổ sung `ground_truth` (tên file đúng) rồi gộp vào tlu_testset.
    """
    fb = await db.get(ChatMessageFeedback, feedback_id)
    if fb is None:
        raise HTTPException(404, "Không tìm thấy phản hồi")
    msg = await db.get(ChatMessage, fb.message_id) if fb.message_id else None
    question = await _question_before(db, msg) if msg else None
    if not question:
        raise HTTPException(400, "Phản hồi không gắn với câu hỏi nào")

    path = _eval_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                existing.add(json.loads(line).get("feedback_id"))
            except ValueError:
                continue
    if feedback_id in existing:
        return {"ok": True, "added": False, "message": "Câu hỏi này đã có trong danh sách ứng viên"}

    record = {
        "feedback_id": feedback_id,
        "question": question,
        "rating": fb.rating,
        "comment": fb.comment,
        "retrieved_sources": _sources(msg.source_docs),
        "ground_truth": [],
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "added": True, "message": "Đã thêm vào danh sách ứng viên bộ đánh giá"}
