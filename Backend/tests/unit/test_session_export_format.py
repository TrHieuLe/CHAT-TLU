"""
test_session_export_format.py — Bản xuất hội thoại (GET /api/sessions/{sid}/export):
  - Giờ hiển thị theo Asia/Ho_Chi_Minh thay vì UTC
  - Bảng đã bị postprocess_answer chuyển thành danh sách được dựng lại thành bảng Markdown
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.models.database import AsyncSessionLocal, ChatMessage, Session, init_db
from app.routers.chat_formatters import (
    _convert_table_block_to_bullets,
    bullets_to_markdown_tables,
    postprocess_answer,
)
from app.routers.sessions import _to_vn_time

USER = {"X-User-ID": "export-format-user"}


# ─── Múi giờ ──────────────────────────────────────────────────────────────────

def test_to_vn_time_naive_utc_from_sqlite():
    vn = _to_vn_time(datetime(2026, 10, 22, 4, 57))
    assert (vn.hour, vn.minute) == (11, 57)
    assert vn.utcoffset().total_seconds() == 7 * 3600


def test_to_vn_time_aware_and_none():
    assert _to_vn_time(None) is None
    vn = _to_vn_time(datetime(2026, 10, 22, 20, 0, tzinfo=timezone.utc))
    assert (vn.day, vn.hour) == (23, 3)  # qua nửa đêm giờ VN


# ─── Dựng lại bảng ────────────────────────────────────────────────────────────

WIDE_TABLE = [
    "| STT | Ngành | Mã ngành | Điểm chuẩn |",
    "|---|---|---|---|",
    *[f"| {i} | Ngành số {i} | 74801{i:02d} | 2{i % 10}.5 |" for i in range(1, 14)],
]


def test_bullets_round_trip_to_table():
    bullets = _convert_table_block_to_bullets(WIDE_TABLE)
    assert bullets.startswith("- **1**\n  - Ngành số 1 | 7480101 | 21.5")

    table = bullets_to_markdown_tables("Điểm chuẩn các ngành:\n" + bullets + "\n\nChúc bạn may mắn.")
    lines = table.splitlines()
    assert lines[0] == "Điểm chuẩn các ngành:"
    assert lines[1] == ""  # bảng tách khỏi đoạn văn
    assert lines[2] == "| Mục | Chi tiết 1 | Chi tiết 2 | Chi tiết 3 |"
    assert lines[3] == "|---|---|---|---|"
    assert lines[4] == "| 1 | Ngành số 1 | 7480101 | 21.5 |"
    assert lines[16] == "| 13 | Ngành số 13 | 7480113 | 23.5 |"
    assert "- **" not in table
    assert table.endswith("Chúc bạn may mắn.")


def test_postprocessed_wide_table_exports_as_table():
    stored = postprocess_answer("\n".join(WIDE_TABLE), "Điểm chuẩn các ngành")
    assert "- **1**" in stored  # đúng dạng đang lưu trong DB
    exported = bullets_to_markdown_tables(stored)
    assert exported.splitlines()[0].startswith("| Mục |")
    assert "| 7 | Ngành số 7 | 7480107 | 27.5 |" in exported


def test_normal_bold_bullets_are_untouched():
    text = "- **Điều kiện 1**\n  - Tích lũy đủ tín chỉ\n- **Điều kiện 2**\n  - GPA từ 2.0 trở lên"
    assert bullets_to_markdown_tables(text) == text


def test_single_bullet_group_is_untouched():
    text = "- **1**\n  - a | b"
    assert bullets_to_markdown_tables(text) == text


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_markdown_uses_vn_time_and_tables():
    await init_db()
    sid = f"export-{uuid.uuid4()}"
    stored = postprocess_answer("\n".join(WIDE_TABLE), "Điểm chuẩn các ngành")

    async with AsyncSessionLocal() as db:
        db.add(Session(
            id=sid,
            user_id=USER["X-User-ID"],
            title="Điểm chuẩn",
            created_at=datetime(2026, 10, 22, 4, 57, tzinfo=timezone.utc),
        ))
        db.add(ChatMessage(session_id=sid, role="user", content="Điểm chuẩn các ngành?"))
        db.add(ChatMessage(session_id=sid, role="model", content=stored))
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=USER) as client:
        md = await client.get(f"/api/sessions/{sid}/export?format=markdown")
        js = await client.get(f"/api/sessions/{sid}/export?format=json")

    assert md.status_code == 200
    text = md.text
    assert "22/10/2026 11:57" in text
    assert "04:57" not in text
    assert "| Mục | Chi tiết 1 | Chi tiết 2 | Chi tiết 3 |" in text
    assert "| 1 | Ngành số 1 | 7480101 | 21.5 |" in text
    assert "- **1**" not in text

    assert js.status_code == 200
    assert js.json()["created_at"].startswith("2026-10-22T11:57:00+07:00")
