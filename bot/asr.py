"""ASR using faster-whisper — transcribes audio chunks from the meeting."""

import os
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()

_model = None


def get_model():
    global _model
    if _model is None:
        size = os.getenv("WHISPER_MODEL", "small")
        print(f"[asr] Loading Whisper model: {size}")
        # device="cuda" uses GPU; compute_type="int8_float16" saves VRAM
        _model = WhisperModel(size, device="cuda", compute_type="int8_float16")
        print("[asr] Whisper model ready.")
    return _model


def transcribe(audio_path: str) -> str:
    """Transcribe an audio file, return plain text."""
    model = get_model()
    segments, info = model.transcribe(audio_path, beam_size=5, language="en")
    text = " ".join(seg.text.strip() for seg in segments)
    return text.strip()


def transcribe_stream(audio_path: str):
    """Generator yielding text segments as they come."""
    model = get_model()
    segments, _ = model.transcribe(audio_path, beam_size=5, language="en")
    for seg in segments:
        yield seg.text.strip()
