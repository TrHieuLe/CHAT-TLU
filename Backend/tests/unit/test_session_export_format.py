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
    restore_markdown_tables,
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


# ─── Lịch sử phiên ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_returns_markdown_tables_for_stored_bullets():
    """Mở lại phiên từ sidebar: câu trả lời đã lưu dạng danh sách (kể cả dữ liệu cũ)
    được trả về thành bảng Markdown; câu hỏi của người dùng giữ nguyên."""
    await init_db()
    sid = f"history-{uuid.uuid4()}"
    stored = postprocess_answer("\n".join(WIDE_TABLE), "Điểm chuẩn các ngành")
    assert "- **1**" in stored
    user_text = "- **1**\n  - a | b\n- **2**\n  - c | d"  # người dùng gõ gì thì giữ nguyên

    async with AsyncSessionLocal() as db:
        db.add(Session(id=sid, user_id=USER["X-User-ID"], title="Điểm chuẩn"))
        db.add(ChatMessage(session_id=sid, role="user", content=user_text,
                           created_at=datetime(2026, 10, 22, 4, 57)))
        db.add(ChatMessage(session_id=sid, role="model", content=stored,
                           created_at=datetime(2026, 10, 22, 4, 58)))
        await db.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=USER) as client:
        r = await client.get(f"/api/sessions/{sid}/history")

    assert r.status_code == 200
    items = r.json()
    assert [m["role"] for m in items] == ["user", "model"]
    assert items[0]["content"] == user_text
    answer = items[1]["content"]
    assert answer.splitlines()[0] == "| Mục | Chi tiết 1 | Chi tiết 2 | Chi tiết 3 |"
    assert "| 7 | Ngành số 7 | 7480107 | 27.5 |" in answer
    assert "- **" not in answer


# ─── <br> trong ô bảng ────────────────────────────────────────────────────────

BR_TABLE = "\n".join([
    "Các điều kiện:",
    "",
    "| STT | Điều kiện | Chi tiết |",
    "| :--- | :--- | :--- |",
    "| 1 | Kỷ luật | - Không bị truy cứu hình sự.<br>- Không bị đình chỉ học tập. |",
    "| 2 | Tín chỉ | - Tích lũy đủ tín chỉ. |",
    "",
    "*Nguồn: QĐ-1226*",
])
BR_ROW = "| 1 | Kỷ luật | • Không bị truy cứu hình sự. • Không bị đình chỉ học tập. |"


def test_postprocess_keeps_table_rows_with_br_in_cell():
    out = postprocess_answer(BR_TABLE, "Điều kiện tốt nghiệp gồm những gì?")
    assert BR_ROW in out.splitlines()
    assert "| 2 | Tín chỉ | - Tích lũy đủ tín chỉ. |" in out.splitlines()


def test_restore_rejoins_rows_split_by_old_br_handling():
    # Bản đã lưu trước khi sửa: <br> bị đổi thành "\n" → dòng 1 bị cắt đôi
    legacy = BR_TABLE.replace("<br>", "\n")
    restored = restore_markdown_tables(legacy).splitlines()
    assert BR_ROW in restored
    assert restored[-1] == "*Nguồn: QĐ-1226*"
    assert restore_markdown_tables(restore_markdown_tables(legacy)) == restore_markdown_tables(legacy)


def test_restore_leaves_non_table_text_alone():
    text = "Đoạn 1\n- ý a | ý b\ntiếp |"
    assert restore_markdown_tables(text) == text
