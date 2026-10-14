"""Phản hồi like/dislike: gắn đúng câu trả lời, xóa semantic cache khi dislike, API quản trị và lịch quét."""
import asyncio
import json
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from app.core.config import settings
from app.models.database import Base, ChatMessage, CrawlRun, get_db
from app.rag.semantic_cache import SemanticCache
from app.routers import crawler as crawler_router


@pytest.fixture
async def session_maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    yield maker
    app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


async def _seed_answer(maker, session_id="s1", question="Học phí bao nhiêu?", answer="Học phí là 500k/tín chỉ."):
    async with maker() as db:
        db.add(ChatMessage(session_id=session_id, role="user", content=question))
        msg = ChatMessage(session_id=session_id, role="model", content=answer,
                          source_docs=json.dumps({"sources": ["QĐ về Học phí.docx"]}))
        db.add(msg)
        await db.commit()
        return msg.id


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_dislike_removes_cached_answer_and_updates_rating(session_maker):
    mid = await _seed_answer(session_maker)
    cache = SemanticCache()
    cache.put("Học phí bao nhiêu?", "Học phí là 500k/tín chỉ.")
    with patch("app.routers.chat.get_semantic_cache", return_value=cache):
        async with _client() as ac:
            r = await ac.post("/api/chat/feedback", json={"session_id": "s1", "message_id": mid, "rating": "like"})
            assert r.status_code == 200 and r.json()["cache_removed"] == 0
            first_id = r.json()["id"]
            r = await ac.post("/api/chat/feedback", json={"session_id": "s1", "message_id": mid, "rating": "dislike"})
            assert r.status_code == 200
            assert r.json()["id"] == first_id  # cập nhật, không tạo bản ghi mới
            assert r.json()["cache_removed"] == 1
    assert cache.get("Học phí bao nhiêu?") is None


@pytest.mark.asyncio
async def test_feedback_rejects_message_of_other_session(session_maker):
    mid = await _seed_answer(session_maker, session_id="s1")
    async with _client() as ac:
        r = await ac.post("/api/chat/feedback", json={"session_id": "s2", "message_id": mid, "rating": "dislike"})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_admin_feedback_list_summary_and_eval_export(session_maker, tmp_path, monkeypatch):
    mid = await _seed_answer(session_maker)
    monkeypatch.setattr(settings, "EVAL_CANDIDATES_PATH", str(tmp_path / "cands.jsonl"))
    async with _client() as ac:
        r = await ac.post("/api/chat/feedback", json={"session_id": "s1", "message_id": mid, "rating": "dislike"})
        fid = r.json()["id"]

        r = await ac.get("/api/admin/feedback", params={"rating": "dislike"})
        data = r.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["question"] == "Học phí bao nhiêu?"
        assert item["answer"] == "Học phí là 500k/tín chỉ."
        assert item["sources"] == ["QĐ về Học phí.docx"]

        r = await ac.get("/api/admin/feedback/summary")
        assert r.json()["totals"] == {"like": 0, "dislike": 1}

        r = await ac.post(f"/api/admin/feedback/{fid}/to-eval")
        assert r.json()["added"] is True
        r = await ac.post(f"/api/admin/feedback/{fid}/to-eval")
        assert r.json()["added"] is False

    lines = (tmp_path / "cands.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["question"] == "Học phí bao nhiêu?"


@pytest.mark.asyncio
async def test_crawl_run_is_recorded_and_listed(session_maker):
    async def fake_crawl(max_articles, progress):
        progress.update(total=2, done=2, new=1, updated=1)

    with patch("app.routers.crawler.crawl_and_ingest_tlu", side_effect=fake_crawl), \
         patch("app.routers.crawler.AsyncSessionLocal", session_maker):
        assert crawler_router.start_crawl(3, trigger="schedule") is True
        await asyncio.wait_for(crawler_router._task, 2)

        async with _client() as ac:
            r = await ac.get("/api/crawler/runs")
            runs = r.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["trigger"] == "schedule"
    assert runs[0]["new"] == 1 and runs[0]["updated"] == 1


@pytest.mark.asyncio
async def test_scheduler_skips_when_job_running():
    calls = []

    def fake_start(max_articles, trigger="manual"):
        calls.append(trigger)
        return False

    with patch("app.routers.crawler.start_crawl", side_effect=fake_start):
        task = asyncio.create_task(crawler_router.crawl_scheduler(1 / 3600 / 100, 5, initial_delay=0))
        await asyncio.sleep(0.05)
        task.cancel()
    assert calls and all(t == "schedule" for t in calls)
