"""
voice.py — API giọng nói: đọc câu trả lời (TTS, edge-tts) và nhận dạng dự phòng (STT, faster-whisper).
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.rate_limit import check_voice_rate_limit
from app.voice import stt_service, tts_service
from app.voice.audio_validator import AudioValidationError, validate_audio
from app.voice.tts_normalizer import normalize_for_speech

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Giới hạn văn bản thô nhận vào (trước chuẩn hoá) — chặn payload khổng lồ
_RAW_TEXT_MAX = 20_000


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_RAW_TEXT_MAX)
    voice: str | None = None
    rate: int = Field(0, ge=tts_service.RATE_MIN, le=tts_service.RATE_MAX)  # % so với tốc độ chuẩn


@router.get("/config")
async def voice_config(user_id: str = Depends(get_current_user_id)):
    return {
        "tts_enabled": settings.TTS_ENABLED,
        "stt_enabled": stt_service.is_available(),
        "default_voice": settings.TTS_DEFAULT_VOICE,
        "voices": [{"id": k, "label": v} for k, v in tts_service.VOICES.items()],
        "rate_min": tts_service.RATE_MIN,
        "rate_max": tts_service.RATE_MAX,
        "stt_max_seconds": settings.STT_MAX_SECONDS,
    }


@router.post("/tts", dependencies=[Depends(check_voice_rate_limit)])
async def text_to_speech(body: TTSRequest, user_id: str = Depends(get_current_user_id)):
    if not settings.TTS_ENABLED:
        raise HTTPException(503, "Tính năng đọc câu trả lời đang tắt")
    voice = body.voice or settings.TTS_DEFAULT_VOICE
    if voice not in tts_service.VOICES:
        raise HTTPException(422, "Giọng đọc không hỗ trợ")

    text = normalize_for_speech(body.text, max_chars=settings.TTS_MAX_CHARS)
    if not text:
        raise HTTPException(422, "Không có nội dung để đọc")

    headers = {"Cache-Control": "private, max-age=3600"}
    cached = tts_service.get_cached(text, voice, body.rate)
    if cached:
        return FileResponse(cached, media_type="audio/mpeg", headers={**headers, "X-TTS-Cache": "hit"})

    try:
        stream = await tts_service.synthesize_stream(text, voice, body.rate)
    except tts_service.TTSError as e:
        raise HTTPException(502, "Không tổng hợp được giọng nói, vui lòng thử lại") from e
    return StreamingResponse(stream, media_type="audio/mpeg", headers={**headers, "X-TTS-Cache": "miss"})


@router.post("/stt", dependencies=[Depends(check_voice_rate_limit)])
async def speech_to_text(audio: UploadFile = File(...), user_id: str = Depends(get_current_user_id)):
    if not stt_service.is_available():
        raise HTTPException(503, "Nhận dạng giọng nói trên server đang tắt")
    max_bytes = settings.STT_MAX_MB * 1024 * 1024
    data = await audio.read(max_bytes + 1)
    try:
        fmt = validate_audio(data, max_bytes)
        text = await stt_service.transcribe(data, fmt)
    except AudioValidationError as e:
        raise HTTPException(e.status_code, str(e)) from e
    except stt_service.STTUnavailableError as e:
        raise HTTPException(503, str(e)) from e
    return {"text": text}
