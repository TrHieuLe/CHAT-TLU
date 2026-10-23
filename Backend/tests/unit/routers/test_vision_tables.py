"""Câu trả lời về ảnh (upload ảnh, hỏi tiếp về ảnh) có bảng rộng: DB giữ bản postprocess
(danh sách) nhưng client phải nhận bảng Markdown — giống lịch sử và semantic cache."""
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from main import app
from app.models.database import AsyncSessionLocal, ChatMessage, Session, init_db
from app.routers import chat
from app.routers.chat_formatters import postprocess_answer

USER = {"X-User-ID": "vision-table-user"}

WIDE_TABLE = "\n".join([
    "| STT | Môn học | Tín chỉ |",
    "|---|---|---|",
    *[f"| {i} | Môn số {i} | {i % 4 + 1} |" for i in range(1, 14)],
])


@pytest.mark.asyncio
async def test_image_upload_returns_markdown_table(tmp_path):
    await init_db()
    from app.llm.llm_service import llm_service

    sid = f"vision-{uuid.uuid4()}"
    with patch.object(chat, "UPLOAD_DIR", tmp_path), \
         patch.object(llm_service, "generate_image_answer", AsyncMock(return_value=WIDE_TABLE)), \
         patch.object(chat, "_maybe_set_title", AsyncMock()):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", headers=USER) as client:
            r = await client.post(
                "/api/chat/image",
                data={"session_id": sid, "question": "Bảng môn học trong ảnh?"},
                files={"image": ("a.png", b"\x89PNG fake", "image/png")},
            )

    assert r.status_code == 200
    answer = r.json()["answer"]
    assert answer.splitlines()[0] == "| Mục | Chi tiết 1 | Chi tiết 2 |"
    assert "| 7 | Môn số 7 | 4 |" in answer
    assert "- **" not in answer

    async with AsyncSessionLocal() as db:
        msg = (await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == sid, ChatMessage.role == "model")
        )).scalar_one()
    assert "- **1**" in msg.content  # bản lưu không đổi


@pytest.mark.asyncio
async def test_image_followup_streams_markdown_table():
    await init_db()
    sid = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Session(id=sid, user_id=USER["X-User-ID"]))
        await db.commit()

    stored = postprocess_answer(WIDE_TABLE, "Liệt kê môn học trong ảnh")
    assert "- **1**" in stored
    with patch.object(chat, "find_last_uploaded_image", AsyncMock(return_value="/images/uploads/x.png")), \
         patch.object(chat, "vision_answer_for_uploaded_image", AsyncMock(return_value=stored)), \
         patch.object(chat, "_maybe_set_title", AsyncMock()):
        events = [e async for e in chat._stream_followup_about_last_image(
            session_id=sid, question="Liệt kê môn học trong ảnh",
        )]

    texts = [json.loads(e[len("data: "):]) for e in events if e.startswith('data: "')]
    assert len(texts) == 1
    assert texts[0].splitlines()[0] == "| Mục | Chi tiết 1 | Chi tiết 2 |"
    assert "| 13 | Môn số 13 | 2 |" in texts[0]
    assert events[-1] == "data: [DONE]\n\n"
