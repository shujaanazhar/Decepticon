"""
TTS using Chatterbox (resemble-ai/chatterbox) — zero-shot voice cloning.

Provide a reference WAV of your voice via VOICE_REFERENCE_WAV in .env.
Falls back to espeak-ng if Chatterbox fails.
"""

import os
import subprocess
import tempfile

from dotenv import load_dotenv

load_dotenv()

VOICE_REFERENCE_WAV = os.getenv("VOICE_REFERENCE_WAV", "")

_model = None


def _load_model():
    global _model
    if _model is not None:
        return _model

    try:
        from chatterbox.tts import ChatterboxTTS
        print("[tts] Loading Chatterbox model on CUDA...")
        _model = ChatterboxTTS.from_pretrained(device="cuda")
        print("[tts] Chatterbox ready.")
        return _model
    except Exception as e:
        print(f"[tts] Chatterbox load failed: {e}")
        return None


def synthesize(text: str, output_path: str = None) -> str:
    """Convert text to speech. Returns path to WAV file."""
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    model = _load_model()

    if model is not None:
        _synthesize_chatterbox(text, output_path, model)
    else:
        _synthesize_espeak(text, output_path)

    return output_path


def _synthesize_chatterbox(text: str, output_path: str, model):
    import torchaudio as ta
    try:
        kwargs = {}
        if VOICE_REFERENCE_WAV and os.path.exists(VOICE_REFERENCE_WAV):
            kwargs["audio_prompt_path"] = VOICE_REFERENCE_WAV

        wav = model.generate(text, cfg_weight=0.3, **kwargs)
        ta.save(output_path, wav, model.sr)
        print(f"[tts] Synthesized {len(text)} chars → {output_path}")
    except Exception as e:
        print(f"[tts] Chatterbox inference error: {e}")
        _synthesize_espeak(text, output_path)


def _synthesize_espeak(text: str, output_path: str):
    """Fallback: espeak-ng (CPU, always available)."""
    subprocess.run(
        ["espeak-ng", "-w", output_path, "-s", "150", text],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not os.path.exists(output_path):
        import wave, struct
        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(struct.pack("<h", 0) * 16000)
