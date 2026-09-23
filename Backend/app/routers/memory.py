from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.models.database import UserMemory, get_db

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/")
async def list_user_memories(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Lấy danh sách tất cả các thực thể trí nhớ mà AI đã ghi nhớ về sinh viên."""
    if not user_id or user_id == "default_user":
        return []

    res = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc())
    )
    memories = res.scalars().all()
    return [
        {
            "id": m.id,
            "key": m.key,
            "value": m.value,
            "confidence": m.confidence,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in memories
    ]


@router.delete("/{key}")
async def delete_single_memory(
    key: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Xóa một thực thể trí nhớ cụ thể (Cổng quên - Forget Gate)."""
    if not user_id or user_id == "default_user":
        raise HTTPException(400, "Cần định danh người dùng")

    res = await db.execute(
        delete(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.key == key,
        )
    )
    await db.commit()
    return {"ok": True, "message": f"Đã xóa ký ức: {key}"}


@router.delete("/")
async def clear_all_memories(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Xóa toàn bộ ký ức dài hạn của người dùng (Reset Cell State)."""
    if not user_id or user_id == "default_user":
        raise HTTPException(400, "Cần định danh người dùng")

    await db.execute(delete(UserMemory).where(UserMemory.user_id == user_id))
    await db.commit()
    return {"ok": True, "message": "Đã làm sạch toàn bộ ký ức dài hạn"}
