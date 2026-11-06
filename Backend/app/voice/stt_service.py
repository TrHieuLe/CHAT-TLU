"""
stt_service.py — Nhận dạng giọng nói dự phòng bằng faster-whisper (chạy local).

Chỉ dùng khi trình duyệt không có Web Speech API (Firefox, một số Safari/iOS).
Model nạp lười ở lần gọi đầu; mỗi lúc chỉ chạy một lượt (CPU nặng). Nếu chưa cài
faster-whisper thì STT báo không khả dụng — không trả transcript giả.
"""
import asyncio
import logging
import os
import tempfile
import threading

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.voice.audio_validator import SUPPORTED_FORMATS, AudioValidationError

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()
_semaphore: asyncio.Semaphore | None = None


class STTUnavailableError(RuntimeError):
    pass


def is_available() -> bool:
    if not settings.STT_ENABLED:
        return False
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def _get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from faster_whisper import WhisperModel
                except Exception as e:
                    raise STTUnavailableError("Chưa cài faster-whisper") from e
                logger.info("Đang nạp Whisper model '%s' (%s/%s)...",
                            settings.STT_MODEL, settings.STT_DEVICE, settings.STT_COMPUTE_TYPE)
                _model = WhisperModel(
                    settings.STT_MODEL,
                    device=settings.STT_DEVICE,
                    compute_type=settings.STT_COMPUTE_TYPE,
                )
    return _model


def _transcribe_file(path: str) -> str:
    model = _get_model()
    segments, info = model.transcribe(
        path,
        language="vi",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    # info có trước khi giải mã segment → từ chối file quá dài mà không tốn công nhận dạng
    if info.duration and info.duration > settings.STT_MAX_SECONDS:
        raise AudioValidationError(
            f"Ghi âm quá dài (tối đa {settings.STT_MAX_SECONDS} giây)", status_code=413
        )
    return " ".join(s.text.strip() for s in segments if s.text.strip()).strip()


async def transcribe(data: bytes, fmt: str) -> str:
    if not is_available():
        raise STTUnavailableError("Nhận dạng giọng nói trên server đang tắt")
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(1)

    fd, path = tempfile.mkstemp(suffix=SUPPORTED_FORMATS.get(fmt, ".bin"))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        async with _semaphore:
            try:
                return await run_in_threadpool(_transcribe_file, path)
            except (AudioValidationError, STTUnavailableError):
                raise
            except Exception as e:  # file hỏng, ffmpeg/PyAV không giải mã được
                logger.warning("Whisper không xử lý được file ghi âm", exc_info=True)
                raise AudioValidationError("Không đọc được file ghi âm") from e
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
