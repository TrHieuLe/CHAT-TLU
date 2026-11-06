"""
audio_validator.py — Kiểm tra file ghi âm gửi lên STT bằng magic bytes.

Học theo AI-SQL: không tin Content-Type hay đuôi file do client gửi. Thời lượng được kiểm
tra sau khi faster-whisper giải mã (định dạng nén như webm/ogg không đọc được header nhanh).
"""

# định dạng → đuôi file tạm (PyAV/ffmpeg dựa vào nội dung, đuôi chỉ để dễ debug)
SUPPORTED_FORMATS: dict[str, str] = {
    "wav": ".wav",
    "webm": ".webm",
    "ogg": ".ogg",
    "mp4": ".m4a",
    "mp3": ".mp3",
    "flac": ".flac",
}


class AudioValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def detect_audio_format(data: bytes) -> str | None:
    if len(data) < 12:
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"\x1a\x45\xdf\xa3":  # EBML (webm/mkv) — MediaRecorder trên Chrome/Edge/Firefox
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[4:8] == b"ftyp":  # MP4/M4A — MediaRecorder trên Safari
        return "mp4"
    if data[:4] == b"fLaC":
        return "flac"
    if data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0 and (data[1] & 0xF6) != 0xF0):
        return "mp3"
    return None


def validate_audio(data: bytes, max_bytes: int) -> str:
    """Trả về định dạng thật của file, hoặc raise AudioValidationError."""
    if not data:
        raise AudioValidationError("File ghi âm rỗng")
    if len(data) > max_bytes:
        raise AudioValidationError(
            f"File ghi âm quá lớn (tối đa {max_bytes // (1024 * 1024)} MB)", status_code=413
        )
    fmt = detect_audio_format(data)
    if fmt is None:
        raise AudioValidationError("Định dạng âm thanh không hỗ trợ", status_code=415)
    return fmt
