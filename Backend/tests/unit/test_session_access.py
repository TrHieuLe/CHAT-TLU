"""
test_session_access.py — Phân quyền phiên trò chuyện:
  - Thiếu X-User-ID → 401 (trừ khi bật ALLOW_ANONYMOUS_USER), không đọc được phiên của ai
  - Phiên "default_user" cũ không hiện cho người khác và không bị người mở trước nhận
  - /api/chat/image kiểm tra ảnh trước khi tạo phiên
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from app.core.config import settings
from app.models.database import Base, ChatMessage, Session, get_db

ALICE = {"X-User-ID": "user-alice"}
BOB = {"X-User-ID": "user-bob"}


@pytest.fixture
async def maker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session_maker
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def client(maker):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed(maker, sid: str, owner: str, text: str = "Câu hỏi riêng tư") -> None:
    async with maker() as db:
        db.add(Session(id=sid, user_id=owner, title=f"phiên của {owner}"))
        db.add(ChatMessage(session_id=sid, role="user", content=text))
        await db.commit()


async def _owner(maker, sid: str) -> str | None:
    async with maker() as db:
        s = (await db.execute(select(Session).where(Session.id == sid))).scalar_one_or_none()
        return s.user_id if s else None


@pytest.mark.asyncio
async def test_missing_user_id_is_rejected_everywhere(maker, client):
    await _seed(maker, "sid-alice", "user-alice")
    await _seed(maker, "sid-legacy", "default_user")

    calls = [
        client.get("/api/sessions/"),
        client.post("/api/sessions/"),
        client.get("/api/sessions/sid-alice/history"),
        client.get("/api/sessions/sid-legacy/history"),
        client.patch("/api/sessions/sid-alice", json={"title": "x"}),
        client.get("/api/sessions/sid-alice/export?format=json"),
        client.delete("/api/sessions/sid-alice"),
        client.post("/api/chat/stream", json={"session_id": "sid-alice", "question": "hi"}),
        client.post(
            "/api/chat/image",
            data={"session_id": "sid-alice"},
            files={"image": ("a.png", b"\x89PNG", "image/png")},
        ),
        client.get("/api/memory/"),
        client.delete("/api/memory/"),
    ]
    for call in calls:
        r = await call
        assert r.status_code == 401, (r.request.method, r.request.url, r.text)

    assert await _owner(maker, "sid-alice") == "user-alice"
    assert await _owner(maker, "sid-legacy") == "default_user"


@pytest.mark.asyncio
async def test_client_cannot_claim_reserved_default_user(maker, client):
    await _seed(maker, "sid-legacy", "default_user")
    for headers, url in (
        ({"X-User-ID": "default_user"}, "/api/sessions/"),
        ({}, "/api/sessions/?user_id=default_user"),
        ({"X-User-ID": "default_user"}, "/api/sessions/sid-legacy/history"),
    ):
        r = await client.get(url, headers=headers)
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_users_see_only_their_own_sessions(maker, client):
    await _seed(maker, "sid-alice", "user-alice")
    await _seed(maker, "sid-bob", "user-bob")
    await _seed(maker, "sid-legacy", "default_user")

    ids_a = [s["id"] for s in (await client.get("/api/sessions/", headers=ALICE)).json()]
    ids_b = [s["id"] for s in (await client.get("/api/sessions/", headers=BOB)).json()]
    assert ids_a == ["sid-alice"]
    assert ids_b == ["sid-bob"]

    r = await client.get("/api/sessions/sid-bob/history", headers=ALICE)
    assert r.status_code == 403
    assert "Câu hỏi riêng tư" not in r.text

    r = await client.get("/api/sessions/sid-alice/history", headers=ALICE)
    assert r.status_code == 200
    assert [m["content"] for m in r.json()] == ["Câu hỏi riêng tư"]

    # Frontend xuất file qua ?user_id= thay cho header
    r = await client.get("/api/sessions/sid-alice/export?format=json&user_id=user-alice")
    assert r.status_code == 200
    r = await client.get("/api/sessions/sid-alice/export?format=json&user_id=user-bob")
    assert r.status_code == 403

    # Bob không được chen câu hỏi vào phiên của Alice
    r = await client.post("/api/chat/stream", headers=BOB, json={"session_id": "sid-alice", "question": "hi"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_legacy_default_user_session_is_hidden_and_not_claimable(maker, client):
    await _seed(maker, "sid-legacy", "default_user", text="Hội thoại cũ")

    r = await client.get("/api/sessions/sid-legacy/history", headers=ALICE)
    assert r.status_code == 403
    assert "Hội thoại cũ" not in r.text
    assert (await client.patch("/api/sessions/sid-legacy", headers=ALICE, json={"title": "của tôi"})).status_code == 403
    assert (await client.get("/api/sessions/sid-legacy/export", headers=ALICE)).status_code == 403
    assert (await client.delete("/api/sessions/sid-legacy", headers=ALICE)).status_code == 403
    r = await client.post("/api/chat/stream", headers=ALICE, json={"session_id": "sid-legacy", "question": "hi"})
    assert r.status_code == 403
    r = await client.post(
        "/api/chat/image",
        headers=ALICE,
        data={"session_id": "sid-legacy"},
        files={"image": ("a.png", b"\x89PNG", "image/png")},
    )
    assert r.status_code == 403

    # Không ai "nhận" được phiên, Bob cũng không thấy
    assert await _owner(maker, "sid-legacy") == "default_user"
    assert (await client.get("/api/sessions/", headers=BOB)).json() == []


@pytest.mark.asyncio
async def test_anonymous_mode_sees_only_default_user_sessions(maker, client, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_ANONYMOUS_USER", True)
    await _seed(maker, "sid-alice", "user-alice")
    await _seed(maker, "sid-legacy", "default_user")

    ids = [s["id"] for s in (await client.get("/api/sessions/")).json()]
    assert ids == ["sid-legacy"]
    assert (await client.get("/api/sessions/sid-legacy/history")).status_code == 200
    assert (await client.get("/api/sessions/sid-alice/history")).status_code == 403


@pytest.mark.asyncio
async def test_history_of_unknown_session_is_empty(maker, client):
    r = await client.get("/api/sessions/chua-co/history", headers=ALICE)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file",
    [
        ("a.gif", b"GIF89a", "image/gif"),
        ("a.png", b"", "image/png"),
        ("a.png", b"0" * (5 * 1024 * 1024 + 1), "image/png"),
    ],
)
async def test_invalid_image_does_not_create_session(maker, client, file):
    r = await client.post(
        "/api/chat/image",
        headers=ALICE,
        data={"session_id": "sid-new"},
        files={"image": file},
    )
    assert r.status_code == 400
    assert await _owner(maker, "sid-new") is None
