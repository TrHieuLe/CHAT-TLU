import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from datetime import datetime, timezone

from main import app
from app.models.database import get_db, Document


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_list_documents(mock_db_session):
    fake_doc = Document(
        id="doc-123",
        filename="quy_che_2024",
        original_name="quy_che_2024.pdf",
        file_type="pdf",
        file_size=102400,
        chunk_count=15,
        status="ok",
        created_at=datetime.now(timezone.utc),
    )
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [fake_doc]
    mock_db_session.execute.return_value = result_mock

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/document/list")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["id"] == "doc-123"
            assert data[0]["filename"] == "quy_che_2024"
            assert data[0]["chunk_count"] == 15
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_document_stats(mock_db_session):
    result_mock = MagicMock()
    result_mock.first.return_value = (5, 120)
    mock_db_session.execute.return_value = result_mock

    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/document/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_documents"] == 5
            assert data["total_chunks"] == 120
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document_success(mock_db_session):
    fake_doc = Document(
        id="doc-to-delete",
        filename="thong_bao",
        original_name="thong_bao.docx",
        file_type="docx",
        file_size=5000,
        chunk_count=3,
        status="ok",
    )
    mock_db_session.get.return_value = fake_doc

    app.dependency_overrides[get_db] = lambda: mock_db_session

    with patch("ingest.delete_doc_by_name", return_value=True) as mock_del_qdrant, \
         patch("app.routers.document.storage_helper.delete_v2", return_value=True):
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.delete("/api/document/doc-to-delete")
                assert resp.status_code == 200
                data = resp.json()
                assert data["ok"] is True
                assert mock_db_session.delete.called
                assert mock_db_session.commit.called
                assert mock_del_qdrant.called
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_document_not_found(mock_db_session):
    mock_db_session.get.return_value = None
    app.dependency_overrides[get_db] = lambda: mock_db_session

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.delete("/api/document/not-exist")
            assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
