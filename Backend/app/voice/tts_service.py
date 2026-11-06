"""
tts_service.py — Đọc câu trả lời bằng edge-tts (giọng neural tiếng Việt của Microsoft).

- Stream các chunk mp3 ra ngay khi edge-tts trả về để client phát sớm.
- Cache file mp3 ra đĩa theo sha256(văn bản đã chuẩn hoá | giọng | tốc độ); chỉ ghi khi
  tổng hợp xong trọn vẹn, và xoá file cũ nhất khi vượt TTS_CACHE_MAX_MB.
"""
import asyncio
import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator

from app.core.config import settings

logger = logging.getLogger(__name__)

VOICES: dict[str, str] = {
    "vi-VN-HoaiMyNeural": "Hoài My (nữ)",
    "vi-VN-NamMinhNeural": "Nam Minh (nam)",
}
RATE_MIN, RATE_MAX = -50, 50
TTS_ATTEMPTS = 3


class TTSError(RuntimeError):
    pass


def _cache_dir() -> Path:
    d = Path(settings.TTS_CACHE_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_key(text: str, voice: str, rate: int) -> str:
    return hashlib.sha256(f"{text}|{voice}|{rate}".encode("utf-8")).hexdigest()


def cache_path(text: str, voice: str, rate: int) -> Path:
    return _cache_dir() / f"{cache_key(text, voice, rate)}.mp3"


def get_cached(text: str, voice: str, rate: int) -> Path | None:
    p = cache_path(text, voice, rate)
    if p.is_file() and p.stat().st_size > 0:
        try:
            os.utime(p)  # LRU: đánh dấu vừa dùng
        except OSError:
            pass
        return p
    return None


def _evict_if_needed() -> None:
    limit = settings.TTS_CACHE_MAX_MB * 1024 * 1024
    if limit <= 0:
        return
    files = [p for p in _cache_dir().glob("*.mp3") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    if total <= limit:
        return
    for p in sorted(files, key=lambda f: f.stat().st_mtime):
        try:
            size = p.stat().st_size
            p.unlink()
            total -= size
        except OSError:
            continue
        if total <= limit:
            break


def _write_cache(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except OSError:
        logger.warning("Không ghi được cache TTS %s", path, exc_info=True)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return
    _evict_if_needed()


def _edge_rate(rate: int) -> str:
    return f"{rate:+d}%"


async def _edge_stream(text: str, voice: str, rate: int) -> AsyncIterator[bytes]:
    import edge_tts  # import muộn để app vẫn chạy khi chưa cài

    communicate = edge_tts.Communicate(text, voice, rate=_edge_rate(rate))
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio" and chunk.get("data"):
            yield chunk["data"]


async def synthesize_stream(text: str, voice: str, rate: int = 0) -> AsyncIterator[bytes]:
    """Stream mp3 cho văn bản đã chuẩn hoá. Ghi cache khi tổng hợp xong.

    Chunk đầu tiên được lấy trước khi trả iterator, để lỗi kết nối edge-tts
    biến thành TTSError (router trả 502) thay vì một response 200 bị cắt ngang.
    """
    if voice not in VOICES:
        raise ValueError(f"Giọng không hỗ trợ: {voice}")
    timeout = settings.TTS_TIMEOUT_SECONDS
    last_error: Exception | None = None
    # Dịch vụ edge-tts thỉnh thoảng trả NoAudioReceived với cùng một câu vẫn đọc được ở lần
    # sau → thử lại vài lần trước khi có chunk đầu (sau đó không thử lại để không lặp audio).
    for attempt in range(TTS_ATTEMPTS):
        gen = _edge_stream(text, voice, rate)
        try:
            first = await asyncio.wait_for(gen.__anext__(), timeout=timeout)
            break
        except Exception as e:  # NoAudioReceived, mạng, timeout, hết dữ liệu...
            last_error = e
            logger.warning("edge-tts lỗi lần %d (%s): %r", attempt + 1, voice, e)
            await gen.aclose()
            if attempt + 1 < TTS_ATTEMPTS:
                await asyncio.sleep(0.3 * (attempt + 1))
    else:
        raise TTSError(f"Lỗi tổng hợp giọng nói: {last_error!r}") from last_error

    async def iterator() -> AsyncIterator[bytes]:
        buf = bytearray(first)
        yield first
        completed = False
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(gen.__anext__(), timeout=timeout)
                except StopAsyncIteration:
                    completed = True
                    break
                buf.extend(chunk)
                yield chunk
        except Exception:
            logger.warning("edge-tts bị ngắt giữa chừng", exc_info=True)
        finally:
            await gen.aclose()
            if completed and buf:
                _write_cache(cache_path(text, voice, rate), bytes(buf))

    return iterator()
