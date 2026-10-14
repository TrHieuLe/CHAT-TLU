"""Smoke test luồng _stream_text_answer (RAG path + semantic cache path) với retriever/LLM giả."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.database import AsyncSessionLocal, ChatMessage, Session, init_db
from app.rag.semantic_cache import SemanticCache
from app.routers import chat


async def _fake_stream(**kwargs):
    for part in ["Điều kiện ", "tốt nghiệp ", "là tích lũy đủ tín chỉ."]:
        yield part


async def _collect(gen) -> list[str]:
    return [ev async for ev in gen]


@pytest.mark.asyncio
async def test_stream_rag_then_cache_hit():
    await init_db()
    session_id = str(uuid.uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Session(id=session_id, user_id="default_user"))
        await db.commit()

    point = SimpleNamespace(payload={"content": "Quy chế...", "doc_name": "quy_che.pdf", "rerank_score": 0.9})
    from app.llm.llm_service import llm_service

    with patch.object(chat._retriever, "retrieve_v3", AsyncMock(return_value=[point])), \
         patch.object(llm_service, "stream_chat_response", _fake_stream), \
         patch.object(llm_service, "generate_title", AsyncMock(return_value="Điều kiện tốt nghiệp")), \
         patch("app.routers.chat.get_semantic_cache", return_value=SemanticCache()) as cache_getter:
        cache = cache_getter.return_value

        events = await _collect(chat._stream_text_answer(
            session_id=session_id, question="Điều kiện tốt nghiệp?", history=[], is_first_turn=True,
        ))
        assert events[-1] == "data: [DONE]\n\n"
        assert any("[SOURCES]" in e for e in events)
        assert cache.get_stats()["cached_entries"] == 1

        # Lần 2 cùng câu hỏi → trúng cache, không gọi retriever
        chat._retriever.retrieve_v3.reset_mock()
        events2 = await _collect(chat._stream_text_answer(
            session_id=str(uuid.uuid4()), question="Điều kiện tốt nghiệp?", history=[],
        ))
        assert events2[-1] == "data: [DONE]\n\n"
        chat._retriever.retrieve_v3.assert_not_called()

    async with AsyncSessionLocal() as db:
        sess = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one()
        assert sess.title == "Điều kiện tốt nghiệp"
        msgs = (await db.execute(select(ChatMessage).where(ChatMessage.session_id == session_id))).scalars().all()
        assert [m.role for m in msgs] == ["user", "model"]
