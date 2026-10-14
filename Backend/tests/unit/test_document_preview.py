import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.models.database import Document, get_db
from app.storage.storage_service import LocalStorageService


@pytest.fixture
def storage(tmp_path):
    svc = LocalStorageService(base_dir=str(tmp_path / "storage"))
    svc.upload_dir = tmp_path / "data"
    svc.upload_dir.mkdir()
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    return svc


def _touch(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_find_file_blocks_path_traversal(storage):
    assert storage.find_file("../.env") is None
    assert storage.find_file(str(storage.upload_dir.parent / ".env")) is None


def test_find_file_prefers_exact_over_fuzzy(storage):
    _touch(storage.upload_dir / "QĐ về tiếng anh CTTT (Copy).doc")
    exact = _touch(storage.upload_dir / "QĐ về tiếng anh CTTT.docx")
    assert storage.find_file("QĐ về tiếng anh CTTT.docx") == exact


def test_find_file_fuzzy_picks_closest_and_ignores_short_stems(storage):
    _touch(storage.upload_dir / "TA.docx")
    close = _touch(storage.upload_dir / "Quy che dao tao 2024.docx")
    _touch(storage.upload_dir / "Quy che dao tao 2024 ban sua doi bo sung.docx")
    assert storage.find_file("Quy che dao tao") == close
    assert storage.find_file("Thong bao TA moi nhat") is None


def test_find_file_nfc_nfd_and_subdirs(storage):
    target = _touch(storage.upload_dir / "crawled" / unicodedata.normalize("NFC", "Học phí.md"))
    assert storage.find_file(unicodedata.normalize("NFD", "Học phí.md")) == target


def test_find_file_without_fuzzy(storage):
    _touch(storage.upload_dir / "Quy che dao tao 2024.docx")
    assert storage.find_file("Quy che dao tao", fuzzy=False) is None


def test_find_file_skips_images(storage):
    _touch(storage.upload_dir / "images" / "uploads" / "abc123.png")
    assert storage.find_file("abc123.png") is None


def _db_returning(doc):
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = doc
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_preview_text_resolves_crawled_doc_by_original_name(tmp_path):
    md = _touch(tmp_path / "TLU_57290_thong-bao-thi.md", "# Thông báo thi\n\nNội dung")
    doc = Document(
        id="d1", filename="TLU_57290_thong-bao-thi", original_name="[Thông báo Web] Thông báo thi",
        file_type="md", file_size=10, chunk_count=2, status="ok",
    )
    app.dependency_overrides[get_db] = lambda: _db_returning(doc)

    def fake_find(name, fuzzy=True):
        return md if name == "TLU_57290_thong-bao-thi.md" else None

    try:
        with patch("app.routers.document.storage_helper.find_file", side_effect=fake_find):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/document/preview-text/[Thông báo Web] Thông báo thi")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["filename"] == "TLU_57290_thong-bao-thi.md"
        assert data["display_name"] == "[Thông báo Web] Thông báo thi"
        assert "Nội dung" in data["content"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_text_404_when_missing():
    app.dependency_overrides[get_db] = lambda: _db_returning(None)
    try:
        with patch("app.routers.document.storage_helper.find_file", return_value=None):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/api/document/preview-text/..%2F..%2F.env")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_crawled_doc_removes_vectors_by_real_file_name():
    doc = Document(
        id="d1", filename="TLU_57290_thong-bao-thi", original_name="[Thông báo Web] Thông báo thi",
        file_type="md", file_size=10, chunk_count=2, status="ok",
    )
    session = AsyncMock()
    session.get.return_value = doc
    app.dependency_overrides[get_db] = lambda: session
    try:
        with patch("ingest.delete_doc_by_name", return_value=True) as del_vec, \
             patch("app.routers.document.storage_helper.delete_v2",
                   side_effect=lambda name: name == "TLU_57290_thong-bao-thi.md") as del_file:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.delete("/api/document/d1")
        assert resp.status_code == 200
        del_vec.assert_any_call("TLU_57290_thong-bao-thi.md")
        del_file.assert_called_with("TLU_57290_thong-bao-thi.md")
    finally:
        app.dependency_overrides.clear()
