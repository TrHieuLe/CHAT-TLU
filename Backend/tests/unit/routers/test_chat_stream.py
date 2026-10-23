"""Smoke test luồng _stream_text_answer (RAG path + semantic cache path) với retriever/LLM giả."""
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from sqlalchemy import select

from app.models.database import AsyncSessionLocal, ChatMessage, Session, init_db
from app.rag.semantic_cache import SemanticCache
from app.routers import chat

POINT = SimpleNamespace(payload={"content": "Quy chế...", "doc_name": "quy_che.pdf", "rerank_score": 0.9})


async def _fake_stream(**kwargs):
    for part in ["Điều kiện ", "tốt nghiệp ", "là tích lũy đủ tín chỉ."]:
        yield part


async def _empty_stream(**kwargs):
    return
    yield  # noqa: unreachable — biến hàm thành async generator rỗng (mọi model đều lỗi)


async def _collect(gen) -> list[str]:
    return [ev async for ev in gen]


async def _new_session() -> str:
    await init_db()
    session_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Session(id=session_id, user_id="default_user"))
        await db.commit()
    return session_id


@contextmanager
def _pipeline(cache: SemanticCache, stream=_fake_stream, points=(POINT,), user_context=""):
    from app.llm.llm_service import llm_service
    vec = np.ones(8, dtype=np.float32)
    with patch.object(chat._retriever, "retrieve_v3", AsyncMock(return_value=list(points))) as retrieve, \
         patch.object(chat._retriever, "embed_query", AsyncMock(return_value=([vec], [{}]))), \
         patch.object(llm_service, "stream_chat_response", stream), \
         patch.object(llm_service, "generate_title", AsyncMock(return_value="Điều kiện tốt nghiệp")), \
         patch("app.memory.memory_service.get_user_cell_state_prompt", AsyncMock(return_value=user_context)), \
         patch("app.routers.chat.get_semantic_cache", return_value=cache):
        yield retrieve


@pytest.mark.asyncio
async def test_stream_rag_then_cache_hit():
    session_id = await _new_session()
    cache = SemanticCache()
    with _pipeline(cache) as retrieve:
        events = await _collect(chat._stream_text_answer(
            session_id=session_id, question="Điều kiện tốt nghiệp?", history=[], is_first_turn=True,
        ))
        assert events[-1] == "data: [DONE]\n\n"
        assert any("[SOURCES]" in e for e in events)
        assert cache.get_stats()["cached_entries"] == 1

        # Cùng câu hỏi, khác từ đệm → trúng cache, không gọi retriever
        retrieve.reset_mock()
        events2 = await _collect(chat._stream_text_answer(
            session_id=str(uuid.uuid4()), question="Cho em hỏi điều kiện tốt nghiệp ạ?", history=[],
        ))
        assert events2[-1] == "data: [DONE]\n\n"
        retrieve.assert_not_called()

    async with AsyncSessionLocal() as db:
        sess = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one()
        assert sess.title == "Điều kiện tốt nghiệp"
        msgs = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id))).scalars().all()
        assert [m.role for m in msgs] == ["user", "model"]


@pytest.mark.asyncio
async def test_llm_failure_not_cached_and_user_sees_message():
    cache = SemanticCache()
    with _pipeline(cache, stream=_empty_stream):
        events = await _collect(chat._stream_text_answer(
            session_id=await _new_session(), question="Điều kiện tốt nghiệp?", history=[],
        ))
    assert any("quá tải" in e for e in events)
    assert cache.get_stats()["cached_entries"] == 0


@pytest.mark.asyncio
async def test_no_context_not_cached():
    cache = SemanticCache()
    with _pipeline(cache, points=()):
        await _collect(chat._stream_text_answer(
            session_id=await _new_session(), question="Điều kiện tốt nghiệp?", history=[],
        ))
    assert cache.get_stats()["cached_entries"] == 0


@pytest.mark.asyncio
async def test_personalized_answer_not_cached_or_served():
    cache = SemanticCache()
    cache.put("Điều kiện tốt nghiệp?", "Câu trả lời chung đã cache sẵn từ trước.")
    with _pipeline(cache, user_context="[HỒ SƠ] Khóa học: K64") as retrieve:
        await _collect(chat._stream_text_answer(
            session_id=await _new_session(), question="Điều kiện tốt nghiệp?", history=[], user_id="u1",
        ))
        retrieve.assert_called_once()  # không dùng câu trả lời cache cho người có hồ sơ riêng
    assert cache.get_stats()["total_lookups"] == 0


@pytest.mark.asyncio
async def test_cache_hit_reuses_cached_title_without_waiting():
    import asyncio
    import time
    from app.llm.llm_service import llm_service

    cache = SemanticCache()
    cache.put("Điều kiện tốt nghiệp?", "Câu trả lời đã cache sẵn đủ dài.", title="Tiêu đề đã cache")

    async def _slow_title(q):
        await asyncio.sleep(5)
        return "Tiêu đề từ Gemini"

    session_id = await _new_session()
    with _pipeline(cache):
        with patch.object(llm_service, "generate_title", _slow_title):
            t0 = time.perf_counter()
            events = await _collect(chat._stream_text_answer(
                session_id=session_id, question="Điều kiện tốt nghiệp?", history=[], is_first_turn=True,
            ))
            assert time.perf_counter() - t0 < 2  # không chờ 5s của Gemini
    assert events[-1] == "data: [DONE]\n\n"
    async with AsyncSessionLocal() as db:
        sess = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one()
        assert sess.title == "Tiêu đề đã cache"


@pytest.mark.asyncio
async def test_rag_answer_cached_with_generated_title():
    cache = SemanticCache()
    with _pipeline(cache):
        await _collect(chat._stream_text_answer(
            session_id=await _new_session(), question="Điều kiện tốt nghiệp?", history=[], is_first_turn=True,
        ))
    entry, _ = cache.get_entry("Điều kiện tốt nghiệp?")
    assert entry.title == "Điều kiện tốt nghiệp"


WIDE_TABLE_ANSWER = "\n".join([
    "Điều kiện tốt nghiệp gồm:",
    "",
    "| STT | Điều kiện | Chi tiết |",
    "|---|---|---|",
    *[f"| {i} | Điều kiện số {i} | Mô tả {i} |" for i in range(1, 14)],
])


def _streamed_text(events: list[str]) -> str:
    import json
    out = []
    for e in events:
        payload = e[len("data: "):].rstrip("\n")
        if payload.startswith("\""):
            out.append(json.loads(payload))
    return "".join(out)


@pytest.mark.asyncio
async def test_cache_hit_streams_markdown_table_not_bullets():
    """Bảng rộng bị postprocess_answer đổi thành danh sách khi lưu cache; lượt trúng cache
    phải gửi lại bảng Markdown cho client như lúc stream lần đầu."""
    async def _table_stream(**kwargs):
        yield WIDE_TABLE_ANSWER

    cache = SemanticCache()
    with _pipeline(cache, stream=_table_stream):
        first = await _collect(chat._stream_text_answer(
            session_id=await _new_session(), question="Điều kiện tốt nghiệp gồm những gì?", history=[],
        ))
        assert "| 1 | Điều kiện số 1 | Mô tả 1 |" in _streamed_text(first)
        entry, _ = cache.get_entry("Điều kiện tốt nghiệp gồm những gì?")
        assert "- **1**" in entry.answer  # cache vẫn giữ bản đã lưu (để dislike khớp nội dung DB)

        session_id = await _new_session()
        second = await _collect(chat._stream_text_answer(
            session_id=session_id, question="Điều kiện tốt nghiệp gồm những gì?", history=[],
        ))
    text = _streamed_text(second)
    assert "| Mục | Chi tiết 1 | Chi tiết 2 |" in text
    assert "| 1 | Điều kiện số 1 | Mô tả 1 |" in text
    assert "| 13 | Điều kiện số 13 | Mô tả 13 |" in text
    assert "- **" not in text

    async with AsyncSessionLocal() as db:
        msgs = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id))).scalars().all()
        assert [m.role for m in msgs] == ["user", "model"]
        assert msgs[1].content == entry.answer
