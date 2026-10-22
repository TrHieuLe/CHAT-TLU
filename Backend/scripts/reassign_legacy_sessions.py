"""
reassign_legacy_sessions.py — Gán các phiên cũ của "default_user" (tạo trước khi có đa người dùng) cho một user.

Sau bản sửa phân quyền, phiên "default_user" không còn hiện cho ai (trừ khi bật ALLOW_ANONYMOUS_USER)
và không bị người mở trước "nhận". Dữ liệu vẫn nằm nguyên trong DB; script này không xóa gì.

Cách dùng (chạy trong thư mục Backend/):
    python scripts/reassign_legacy_sessions.py                       # chỉ liệt kê
    python scripts/reassign_legacy_sessions.py --to <X-User-ID>      # gán tất cả cho user đó
    python scripts/reassign_legacy_sessions.py --to <X-User-ID> --ids <sid1> <sid2>

X-User-ID của trình duyệt xem trong DevTools: localStorage["studybot_user_id"].
"""
import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, select, update  # noqa: E402

from app.core.auth import DEFAULT_USER_ID, _USER_ID_RE  # noqa: E402
from app.models.database import AsyncSessionLocal, ChatMessage, Session  # noqa: E402


async def main(to_user: str | None, ids: list[str] | None) -> None:
    async with AsyncSessionLocal() as db:
        query = (
            select(Session, func.count(ChatMessage.id))
            .outerjoin(ChatMessage, ChatMessage.session_id == Session.id)
            .where(Session.user_id == DEFAULT_USER_ID)
            .group_by(Session.id)
            .order_by(Session.updated_at.desc())
        )
        if ids:
            query = query.where(Session.id.in_(ids))
        rows = (await db.execute(query)).all()

        print(f"Phiên của {DEFAULT_USER_ID}: {len(rows)}")
        for s, n in rows:
            print(f"  - {s.id}  {s.updated_at:%Y-%m-%d %H:%M}  {n:>3} tin  {s.title}")

        if not to_user or not rows:
            return
        await db.execute(
            update(Session)
            .where(Session.id.in_([s.id for s, _ in rows]))
            .values(user_id=to_user)
        )
        await db.commit()
        print(f"Đã gán {len(rows)} phiên cho {to_user}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows mặc định cp1252
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to", dest="to_user", help="X-User-ID nhận phiên; bỏ trống = chỉ liệt kê")
    parser.add_argument("--ids", nargs="+", help="Chỉ gán các phiên này (mặc định: tất cả)")
    args = parser.parse_args()
    if args.to_user and (args.to_user == DEFAULT_USER_ID or not _USER_ID_RE.match(args.to_user)):
        parser.error("--to không hợp lệ")
    asyncio.run(main(args.to_user, args.ids))
