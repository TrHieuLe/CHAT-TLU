from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.core import rate_limit
from app.core.config import settings
from app.voice import stt_service, tts_service

H = {"X-User-ID": "user-voice"}
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TTS_CACHE_DIR", str(tmp_path / "tts"))
    monkeypatch.setattr(settings, "TTS_ENABLED", True)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
def fake_edge(monkeypatch):
    calls = []

    async def fake_stream(text, voice, rate):
        calls.append((text, voice, rate))
        yield b"ID3fake-"
        yield b"mp3-data"

    monkeypatch.setattr(tts_service, "_edge_stream", fake_stream)
    return calls


@pytest.fixture
def mock_whisper(monkeypatch):
    monkeypatch.setattr(stt_service, "is_available", lambda: True)
    model = MagicMock()
    monkeypatch.setattr(stt_service, "_get_model", lambda: model)
    return model


@pytest.mark.asyncio
async def test_config(client):
    async with client as ac:
        r = await ac.get("/api/voice/config", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["default_voice"] in {v["id"] for v in body["voices"]}


@pytest.mark.asyncio
async def test_requires_user_id(client):
    async with client as ac:
        r = await ac.post("/api/voice/tts", json={"text": "xin chào"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_tts_streams_then_hits_cache(client, fake_edge):
    async with client as ac:
        r1 = await ac.post("/api/voice/tts", json={"text": "**Xin chào** 50%"}, headers=H)
        r2 = await ac.post("/api/voice/tts", json={"text": "**Xin chào** 50%"}, headers=H)
    assert r1.status_code == 200 and r1.headers["content-type"] == "audio/mpeg"
    assert r1.content == b"ID3fake-mp3-data"
    assert r1.headers["x-tts-cache"] == "miss"
    assert r2.status_code == 200 and r2.headers["x-tts-cache"] == "hit"
    assert r2.content == r1.content
    assert len(fake_edge) == 1
    # edge-tts nhận văn bản đã chuẩn hoá
    assert fake_edge[0][0] == "Xin chào 50 phần trăm."


@pytest.mark.asyncio
async def test_tts_rejects_bad_voice_rate_and_empty(client, fake_edge):
    async with client as ac:
        r1 = await ac.post("/api/voice/tts", json={"text": "a", "voice": "en-US-Bad"}, headers=H)
        r2 = await ac.post("/api/voice/tts", json={"text": "a", "rate": 90}, headers=H)
        r3 = await ac.post("/api/voice/tts", json={"text": "** ##"}, headers=H)
    assert (r1.status_code, r2.status_code, r3.status_code) == (422, 422, 422)
    assert fake_edge == []


@pytest.mark.asyncio
async def test_tts_upstream_error_returns_502(client, monkeypatch):
    async def broken(text, voice, rate):
        raise ConnectionError("no network")
        yield b""  # biến hàm thành async generator

    monkeypatch.setattr(tts_service, "_edge_stream", broken)
    async with client as ac:
        r = await ac.post("/api/voice/tts", json={"text": "xin chào"}, headers=H)
    assert r.status_code == 502


@pytest.mark.asyncio
async def test_tts_retries_when_no_audio_received(client, monkeypatch):
    calls = {"n": 0}

    async def flaky(text, voice, rate):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("No audio was received")
        yield b"ID3ok"

    monkeypatch.setattr(tts_service, "_edge_stream", flaky)
    async with client as ac:
        r = await ac.post("/api/voice/tts", json={"text": "xin chào"}, headers=H)
    assert r.status_code == 200 and r.content == b"ID3ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_tts_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", False)
    async with client as ac:
        r = await ac.post("/api/voice/tts", json={"text": "xin chào"}, headers=H)
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_stt_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "STT_ENABLED", False)
    async with client as ac:
        r = await ac.post("/api/voice/stt", files={"audio": ("a.webm", WEBM, "audio/webm")}, headers=H)
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_stt_rejects_non_audio(client, mock_whisper):
    async with client as ac:
        r = await ac.post("/api/voice/stt", files={"audio": ("a.webm", b"hello world!!", "audio/webm")}, headers=H)
    assert r.status_code == 415
    mock_whisper.transcribe.assert_not_called()


@pytest.mark.asyncio
async def test_stt_transcribes_with_mock_model(client, mock_whisper):
    seg = MagicMock()
    seg.text = " học phí bao nhiêu "
    mock_whisper.transcribe.return_value = ([seg], MagicMock(duration=3.0))
    async with client as ac:
        r = await ac.post("/api/voice/stt", files={"audio": ("a.webm", WEBM, "audio/webm")}, headers=H)
    assert r.status_code == 200
    assert r.json() == {"text": "học phí bao nhiêu"}
    assert mock_whisper.transcribe.call_args.kwargs["language"] == "vi"


@pytest.mark.asyncio
async def test_stt_rejects_too_long(client, mock_whisper):
    mock_whisper.transcribe.return_value = ([], MagicMock(duration=settings.STT_MAX_SECONDS + 5))
    async with client as ac:
        r = await ac.post("/api/voice/stt", files={"audio": ("a.webm", WEBM, "audio/webm")}, headers=H)
    assert r.status_code == 413


def test_voice_and_chat_rate_limit_buckets_are_separate(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(settings, "VOICE_RATE_LIMIT_PER_MINUTE", 1)
    rate_limit.reset()
    req = MagicMock()
    req.headers = {}
    req.client.host = "1.2.3.4"
    rate_limit.check_rate_limit(req, "u1")
    rate_limit.check_voice_rate_limit(req, "u1")  # bucket riêng: không bị chặn bởi chat
    with pytest.raises(Exception) as exc:
        rate_limit.check_voice_rate_limit(req, "u1")
    assert exc.value.status_code == 429
    rate_limit.reset()


def test_cache_eviction(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TTS_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "TTS_CACHE_MAX_MB", 1)
    big = b"x" * (600 * 1024)
    tts_service._write_cache(tts_service.cache_path("a", "v", 0), big)
    tts_service._write_cache(tts_service.cache_path("b", "v", 0), big)
    assert len(list(tmp_path.glob("*.mp3"))) == 1
