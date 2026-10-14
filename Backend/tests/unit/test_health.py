from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_health_ok_when_qdrant_reachable():
    fake = AsyncMock(return_value=SimpleNamespace(points_count=42))
    with patch("app.routers.chat._async.get_collection", fake):
        async with _client() as ac:
            r = await ac.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["database"] == "ok" and body["qdrant_chunks"] == 42


@pytest.mark.asyncio
async def test_health_503_when_qdrant_down():
    with patch("app.routers.chat._async.get_collection", AsyncMock(side_effect=ConnectionError())):
        async with _client() as ac:
            r = await ac.get("/health")
    assert r.status_code == 503
    assert r.json()["qdrant"].startswith("error")
