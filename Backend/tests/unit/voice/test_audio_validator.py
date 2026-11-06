import pytest

from app.voice.audio_validator import AudioValidationError, detect_audio_format, validate_audio

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
MP4 = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 32
OGG = b"OggS" + b"\x00" * 32


@pytest.mark.parametrize("data,fmt", [(WAV, "wav"), (WEBM, "webm"), (MP4, "mp4"), (OGG, "ogg")])
def test_detects_formats(data, fmt):
    assert detect_audio_format(data) == fmt


def test_rejects_spoofed_file():
    with pytest.raises(AudioValidationError) as e:
        validate_audio(b"<html>not audio</html>", 1024)
    assert e.value.status_code == 415


def test_rejects_empty_and_too_large():
    with pytest.raises(AudioValidationError):
        validate_audio(b"", 1024)
    with pytest.raises(AudioValidationError) as e:
        validate_audio(WEBM + b"\x00" * 2000, 1024)
    assert e.value.status_code == 413


def test_accepts_valid():
    assert validate_audio(WEBM, 1024) == "webm"
