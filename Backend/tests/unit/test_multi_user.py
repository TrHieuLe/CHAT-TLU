import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from app.models.database import Base, get_db


@pytest.fixture
async def multi_user_db():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_multi_user_session_isolation(multi_user_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. User A tạo session
        res_a = await client.post("/api/sessions/", headers={"X-User-ID": "user-alice"})
        assert res_a.status_code == 200
        session_a_id = res_a.json()["id"]

        # 2. User B tạo session
        res_b = await client.post("/api/sessions/", headers={"X-User-ID": "user-bob"})
        assert res_b.status_code == 200
        session_b_id = res_b.json()["id"]

        # 3. User A lấy danh sách sessions
        list_a = await client.get("/api/sessions/", headers={"X-User-ID": "user-alice"})
        assert list_a.status_code == 200
        ids_a = [s["id"] for s in list_a.json()]
        assert session_a_id in ids_a
        assert session_b_id not in ids_a

        # 4. User B lấy danh sách sessions
        list_b = await client.get("/api/sessions/", headers={"X-User-ID": "user-bob"})
        assert list_b.status_code == 200
        ids_b = [s["id"] for s in list_b.json()]
        assert session_b_id in ids_b
        assert session_a_id not in ids_b

        # 5. User B cố gắng xem lịch sử session của User A -> Bị từ chối 403
        history_forbidden = await client.get(
            f"/api/sessions/{session_a_id}/history",
            headers={"X-User-ID": "user-bob"},
        )
        assert history_forbidden.status_code == 403

        # 6. User B cố gắng đổi tên session của User A -> Bị từ chối 403
        rename_forbidden = await client.patch(
            f"/api/sessions/{session_a_id}",
            headers={"X-User-ID": "user-bob"},
            json={"title": "Hacked Title"},
        )
        assert rename_forbidden.status_code == 403

        # 7. User B cố gắng xoá session của User A -> Bị từ chối 403
        delete_forbidden = await client.delete(
            f"/api/sessions/{session_a_id}",
            headers={"X-User-ID": "user-bob"},
        )
        assert delete_forbidden.status_code == 403

        # 8. User A tự đổi tên session của mình -> Thành công
        rename_ok = await client.patch(
            f"/api/sessions/{session_a_id}",
            headers={"X-User-ID": "user-alice"},
            json={"title": "Đoạn chat của Alice"},
        )
        assert rename_ok.status_code == 200
        assert rename_ok.json()["title"] == "Đoạn chat của Alice"
