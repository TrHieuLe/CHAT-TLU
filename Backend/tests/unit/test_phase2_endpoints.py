"""
test_phase2_endpoints.py — Unit tests cho các tính năng mới trong Giai đoạn 2:
  - AI Title generation & token count
  - Rename session (PATCH /api/sessions/{sid})
  - Export chat markdown & json (GET /api/sessions/{sid}/export)
  - Submit feedback (POST /api/chat/feedback)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from main import app
from app.models.database import Session, ChatMessage, AsyncSessionLocal, init_db
from app.llm.llm_service import llm_service


class TestLLMServiceUtilities:
    def test_count_tokens(self):
        assert llm_service.count_tokens("") == 0
        assert llm_service.count_tokens("Xin chào các bạn sinh viên TLU") > 0

    @pytest.mark.asyncio
    async def test_generate_title_fallback(self):
        # Khi không có client hoặc API trả về lỗi -> fallback chuỗi cắt ngắn
        with patch.object(llm_service, "_get_client", return_value=None):
            title = await llm_service.generate_title("Quy chế thi lại và học cải thiện điểm")
            assert "Quy chế thi lại" in title


@pytest.mark.asyncio
class TestPhase2Endpoints:
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        await init_db()

    async def test_session_rename(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Tạo session mới
            res = await client.post("/api/sessions/")
            assert res.status_code == 200
            sid = res.json()["id"]

            # 2. Đổi tên session
            new_title = "Quy chế đào tạo mới 2026"
            patch_res = await client.patch(
                f"/api/sessions/{sid}",
                json={"title": new_title},
            )
            assert patch_res.status_code == 200
            assert patch_res.json()["title"] == new_title

            # 3. Kiểm tra rỗng -> 400
            bad_res = await client.patch(
                f"/api/sessions/{sid}",
                json={"title": "   "},
            )
            assert bad_res.status_code == 400

    async def test_session_export(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Tạo session
            res = await client.post("/api/sessions/")
            sid = res.json()["id"]

            # 2. Thêm tin nhắn vào DB
            async with AsyncSessionLocal() as db:
                db.add(ChatMessage(session_id=sid, role="user", content="Em muốn hỏi về học bổng?"))
                db.add(ChatMessage(session_id=sid, role="model", content="Học bổng loại Giỏi yêu cầu GPA >= 3.2."))
                await db.commit()

            # 3. Export JSON
            export_json = await client.get(f"/api/sessions/{sid}/export?format=json")
            assert export_json.status_code == 200
            data = export_json.json()
            assert len(data["messages"]) == 2

            # 4. Export Markdown
            export_md = await client.get(f"/api/sessions/{sid}/export?format=markdown")
            assert export_md.status_code == 200
            text = export_md.text
            assert "Cuộc trò chuyện" in text
            assert "Em muốn hỏi về học bổng?" in text
            assert "Học bổng loại Giỏi" in text

    async def test_submit_feedback(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Submit Like
            fb_res = await client.post(
                "/api/chat/feedback",
                json={
                    "session_id": "test-session-123",
                    "rating": "like",
                    "comment": "Câu trả lời rất rõ ràng",
                },
            )
            assert fb_res.status_code == 200
            assert fb_res.json()["ok"] is True
            assert "id" in fb_res.json()

            # 2. Submit Dislike
            dis_res = await client.post(
                "/api/chat/feedback",
                json={
                    "session_id": "test-session-123",
                    "rating": "dislike",
                    "comment": "Thông tin học phí chưa cập nhật năm 2026",
                },
            )
            assert dis_res.status_code == 200

            # 3. Invalid rating -> 400
            bad_rating = await client.post(
                "/api/chat/feedback",
                json={"session_id": "s1", "rating": "awesome"},
            )
            assert bad_rating.status_code == 400
