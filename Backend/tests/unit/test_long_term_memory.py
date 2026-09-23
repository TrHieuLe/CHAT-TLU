import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from main import app
from app.models.database import Base, get_db
from app.memory.memory_service import (
    extract_student_profile,
    update_user_memories,
    get_user_cell_state_prompt,
)


def test_extract_student_profile_patterns():
    # 1. Khóa + Ngành
    res1 = extract_student_profile("Mình là sinh viên K64 học ngành kỹ thuật phần mềm")
    assert res1.get("khoa_hoc") == "K64"
    assert res1.get("nganh") == "Kỹ thuật phần mềm"

    # 2. Khoa + Target CPA
    res2 = extract_student_profile("Em thuộc khoa công nghệ thông tin, mục tiêu cpa là 3.2")
    assert res2.get("khoa") == "Công nghệ thông tin"
    assert res2.get("muc_tieu_cpa") == "3.2"

    # 3. Môn nợ / học lại
    res3 = extract_student_profile("Kỳ này mình nợ môn Giải tích 1 cần học lại")
    assert "giải tích 1" in res3.get("mon_can_cai_thien", "").lower()


@pytest.fixture
async def memory_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
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
    yield session_maker
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_cell_state_and_endpoints(memory_db):
    transport = ASGITransport(app=app)
    user_id = "student_tlu_123"

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ban đầu chưa có ký ức nào
        res_list = await client.get("/api/memory/", headers={"X-User-ID": user_id})
        assert res_list.status_code == 200
        assert res_list.json() == []

        # Cập nhật ký ức qua memory_service
        async with memory_db() as db:
            count = await update_user_memories(
                user_id=user_id,
                text="Em là sinh viên K64 khoa công nghệ thông tin",
                db=db,
            )
            assert count >= 2

            # Đọc Cell State Prompt
            prompt = await get_user_cell_state_prompt(user_id=user_id, db=db)
            assert "K64" in prompt
            assert "Công nghệ thông tin" in prompt

        # Kiểm tra qua API GET /api/memory/
        res_list2 = await client.get("/api/memory/", headers={"X-User-ID": user_id})
        assert res_list2.status_code == 200
        items = res_list2.json()
        assert len(items) >= 2
        keys = [item["key"] for item in items]
        assert "khoa_hoc" in keys
        assert "khoa" in keys

        # Xóa 1 ký ức cụ thể (Forget Gate)
        res_del_one = await client.delete("/api/memory/khoa", headers={"X-User-ID": user_id})
        assert res_del_one.status_code == 200
        assert res_del_one.json()["ok"] is True

        res_list3 = await client.get("/api/memory/", headers={"X-User-ID": user_id})
        keys_after = [item["key"] for item in res_list3.json()]
        assert "khoa" not in keys_after
        assert "khoa_hoc" in keys_after

        # Xóa toàn bộ ký ức (Reset)
        res_del_all = await client.delete("/api/memory/", headers={"X-User-ID": user_id})
        assert res_del_all.status_code == 200

        res_list4 = await client.get("/api/memory/", headers={"X-User-ID": user_id})
        assert res_list4.json() == []
