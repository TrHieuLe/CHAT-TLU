import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.models.database import ChatMessage, Session, get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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
    query = select(Session)
    if user_id != "default_user":
        query = query.where((Session.user_id == user_id) | (Session.user_id == "default_user"))
    query = query.order_by(Session.updated_at.desc())
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
    if session_obj:
        if session_obj.user_id == "default_user" and user_id != "default_user":
            session_obj.user_id = user_id
            await db.commit()
        elif user_id != "default_user" and session_obj.user_id != user_id:
            raise HTTPException(403, "Bạn không có quyền truy cập phiên này")
    r = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == sid)
        .order_by(ChatMessage.created_at.asc())
    )

    items = []
    for m in r.scalars().all():
      meta = _parse_meta(m.source_docs)
      items.append({
          "role": m.role,
          "content": m.content,
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
    if s.user_id != "default_user" and user_id != "default_user" and s.user_id != user_id:
        raise HTTPException(403, "Bạn không có quyền sửa phiên này")
    s.title = title
    if s.user_id == "default_user" and user_id != "default_user":
        s.user_id = user_id
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
    if s.user_id != "default_user" and user_id != "default_user" and s.user_id != user_id:
        raise HTTPException(403, "Bạn không có quyền xuất phiên này")

    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == sid)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = res.scalars().all()

    if format == "json":
        return {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
        }

    # Format Markdown
    time_str = s.created_at.strftime('%d/%m/%Y %H:%M') if s.created_at else ''
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
        md_lines.append(m.content)
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
    if s.user_id != "default_user" and user_id != "default_user" and s.user_id != user_id:
        raise HTTPException(403, "Bạn không có quyền xóa phiên này")

    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == sid))
    await db.execute(delete(Session).where(Session.id == sid))
    await db.commit()
    return {"ok": True}