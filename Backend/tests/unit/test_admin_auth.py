"""Kiểm tra bảo vệ endpoint quản trị, định dạng user ID, rate limit và CORS."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.core import rate_limit
from app.core.config import settings
from app.models.database import get_db

ADMIN_KEY = "test-admin-secret"

ADMIN_ENDPOINTS = [
    ("GET", "/api/document/list"),
    ("GET", "/api/document/stats"),
    ("DELETE", "/api/document/some-id"),
    ("GET", "/api/crawler/status"),
    ("POST", "/api/crawler/run"),
    ("GET", "/api/chat/cache/stats"),
    ("DELETE", "/api/chat/cache/clear"),
    ("GET", "/api/chat/perf/stats"),
    ("DELETE", "/api/chat/perf/clear"),
]


@pytest.fixture
def admin_auth_on(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_AUTH_DISABLED", False)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", ADMIN_KEY)


@pytest.fixture
def client():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.one.return_value = (0, 0)
    db.execute.return_value = result
    db.get.return_value = None
    app.dependency_overrides[get_db] = lambda: db
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_admin_endpoint_requires_key(admin_auth_on, client, method, path):
    async with client as ac:
        r = await ac.request(method, path)
        assert r.status_code == 401
        r = await ac.request(method, path, headers={"X-Admin-Key": "wrong"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_endpoint_with_valid_key(admin_auth_on, client):
    async with client as ac:
        r = await ac.get("/api/document/list", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200
        r = await ac.get("/api/chat/perf/stats", headers={"X-Admin-Key": ADMIN_KEY})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_admin_endpoint_rejected_when_key_not_configured(monkeypatch, client):
    monkeypatch.setattr(settings, "ADMIN_AUTH_DISABLED", False)
    monkeypatch.setattr(settings, "ADMIN_API_KEY", None)
    async with client as ac:
        r = await ac.get("/api/document/list", headers={"X-Admin-Key": "anything"})
        assert r.status_code == 503


@pytest.mark.asyncio
async def test_public_document_preview_does_not_need_key(admin_auth_on, client):
    async with client as ac:
        r = await ac.get("/api/document/preview-text/khong-ton-tai.pdf")
        assert r.status_code not in (401, 403, 503)


@pytest.mark.asyncio
async def test_invalid_user_id_rejected(client):
    async with client as ac:
        r = await ac.get("/api/sessions/", headers={"X-User-ID": "x" * 200})
        assert r.status_code == 400
        r = await ac.get("/api/sessions/", headers={"X-User-ID": "<script>"})
        assert r.status_code == 400


def test_rate_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    rate_limit.reset()
    req = MagicMock()
    req.headers = {}
    req.client.host = "1.2.3.4"
    rate_limit.check_rate_limit(req, "u1")
    rate_limit.check_rate_limit(req, "u1")
    with pytest.raises(Exception) as exc:
        rate_limit.check_rate_limit(req, "u1")
    assert exc.value.status_code == 429
    # user khác không bị ảnh hưởng
    rate_limit.check_rate_limit(req, "u2")
    rate_limit.reset()


@pytest.mark.asyncio
async def test_cors_rejects_unknown_origin(client):
    async with client as ac:
        r = await ac.get("/", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in r.headers
        r = await ac.get("/", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
