import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import ensure_session_owner, get_current_user_id
from app.models.database import ChatMessage, Session, get_db
from app.routers.chat_formatters import restore_markdown_tables

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Giờ Việt Nam (Asia/Ho_Chi_Minh, UTC+7, không có giờ mùa hè). Dùng offset cố định
# để không phụ thuộc dữ liệu tzdata của hệ điều hành (Windows / image Docker slim).
VN_TZ = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")


def _to_vn_time(dt: datetime | None) -> datetime | None:
    """created_at lưu theo UTC; SQLite trả về datetime không kèm múi giờ."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VN_TZ)


def _parse_meta(raw: str | None) -> dict:
    if not raw:
        return {}

    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"sources": [s for s in raw.split("|") if s]}


@router.post("/")
async def create_session(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    s = Session(id=str(uuid.uuid4()), user_id=user_id)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {
        "id": s.id,
        "title": s.title,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


@router.get("/")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    query = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.updated_at.desc())
    )
    r = await db.execute(query)
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in r.scalars().all()
    ]


@router.get("/{sid}/history")
async def get_history(
    sid: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    r = await db.execute(select(Session).where(Session.id == sid))
    session_obj = r.scalar_one_or_none()
    if session_obj is None:
        # Phiên mới trên client, chưa gửi câu hỏi nào
        return []
    ensure_session_owner(session_obj.user_id, user_id)
    r = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == sid)
        .order_by(ChatMessage.created_at.asc())
    )

    items = []
    for m in r.scalars().all():
      meta = _parse_meta(m.source_docs)
      items.append({
          "id": m.id,
          "role": m.role,
          # Bảng rộng đã bị postprocess_answer đổi thành danh sách khi lưu → dựng lại bảng
          # để phiên mở lại hiển thị giống lúc stream (áp dụng cả cho dữ liệu cũ).
          "content": restore_markdown_tables(m.content) if m.role != "user" else m.content,
          "sources": meta.get("sources", []),
          "images": meta.get("images", []),
      })

    return items


from pydantic import BaseModel
from fastapi.responses import Response


class UpdateSessionRequest(BaseModel):
    title: str


@router.patch("/{sid}")
async def rename_session(
    sid: str,
    req: UpdateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    title = req.title.strip()
    if not title:
        raise HTTPException(400, "Tiêu đề không được để trống")
    r = await db.execute(select(Session).where(Session.id == sid))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Không tìm thấy session")
    ensure_session_owner(s.user_id, user_id, "sửa")
    s.title = title
    await db.commit()
    return {"id": s.id, "title": s.title}


@router.get("/{sid}/export")
async def export_session(
    sid: str,
    format: str = "markdown",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    r = await db.execute(select(Session).where(Session.id == sid))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Không tìm thấy session")
    ensure_session_owner(s.user_id, user_id, "xuất")

    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == sid)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = res.scalars().all()

    if format == "json":
        def _iso(dt):
            vn = _to_vn_time(dt)
            return vn.isoformat() if vn else None

        return {
            "id": s.id,
            "title": s.title,
            "created_at": _iso(s.created_at),
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": _iso(m.created_at),
                }
                for m in messages
            ],
        }

    # Format Markdown
    created_vn = _to_vn_time(s.created_at)
    time_str = f"{created_vn:%d/%m/%Y %H:%M} (giờ Việt Nam)" if created_vn else ""
    md_lines = [
        f"# Cuộc trò chuyện: {s.title}",
        f"*Thời gian: {time_str}*",
        "",
        "---",
        "",
    ]
    for m in messages:
        sender = "👤 **Sinh viên**" if m.role == "user" else "🤖 **StudyBot**"
        md_lines.append(f"### {sender}")
        content = m.content or ""
        md_lines.append(restore_markdown_tables(content) if m.role != "user" else content)
        md_lines.append("")

    content = "\n".join(md_lines)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=chat_{sid[:8]}.md"
        }
    )


@router.delete("/{sid}")
async def del_session(
    sid: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    r = await db.execute(select(Session).where(Session.id == sid))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Không tìm thấy session")
    ensure_session_owner(s.user_id, user_id, "xóa")

    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.commit()
    return {"ok": True}
