"""
Central configuration and backend selection.

Two backends can attend a meeting:

  local     Playwright drives a real Chrome, PulseAudio virtual devices carry
            the audio, Whisper transcribes, Ollama decides what to say, and
            Chatterbox speaks it in your cloned voice. Free, needs a GPU.

  attendee  The hosted Attendee API sends a bot and streams transcripts back
            over a webhook. Almost no local resources, but listen-only and
            free for the first 5 hours only.

Selection is automatic: set ATTENDEE in .env and you get the attendee backend,
leave it blank and everything runs locally. Set BOT_BACKEND to force one.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _float(name: str, default: float) -> float:
    raw = _flag(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"[config] {name}={raw!r} is not a number — using {default}")
        return default


def _int(name: str, default: int) -> int:
    return int(_float(name, default))


# ── Backend selection ────────────────────────────────────────────────────────
LOCAL = "local"
ATTENDEE = "attendee"
VALID_BACKENDS = (LOCAL, ATTENDEE)

BOT_BACKEND = _flag("BOT_BACKEND", "auto").lower()
ATTENDEE_API_KEY = _flag("ATTENDEE")


class ConfigError(RuntimeError):
    """Raised when the configuration cannot produce a working backend."""


def resolve_backend() -> str:
    """Return the backend name to run, or raise ConfigError explaining why not."""
    if BOT_BACKEND in ("", "auto"):
        return ATTENDEE if ATTENDEE_API_KEY else LOCAL

    if BOT_BACKEND not in VALID_BACKENDS:
        raise ConfigError(
            f"BOT_BACKEND={BOT_BACKEND!r} is not valid. "
            f"Use one of: auto, {', '.join(VALID_BACKENDS)}."
        )

    if BOT_BACKEND == ATTENDEE and not ATTENDEE_API_KEY:
        raise ConfigError(
            "BOT_BACKEND=attendee but ATTENDEE is not set in .env. "
            "Add your key from app.attendee.dev, or use BOT_BACKEND=local."
        )

    return BOT_BACKEND


def describe_selection() -> str:
    """One line explaining which backend was chosen and why."""
    backend = resolve_backend()
    if BOT_BACKEND in ("", "auto"):
        reason = "ATTENDEE key found" if ATTENDEE_API_KEY else "no ATTENDEE key, staying local"
        return f"backend={backend} (auto: {reason})"
    return f"backend={backend} (forced via BOT_BACKEND)"


# ── Shared ───────────────────────────────────────────────────────────────────
BOT_NAME = _flag("BOT_NAME", "Decepticon")
TRANSCRIPTS_DIR = _flag("TRANSCRIPTS_DIR", "transcripts")
POLL_INTERVAL_SEC = _int("POLL_INTERVAL_SEC", 30)
JOIN_EARLY_SEC = _float("JOIN_EARLY_SEC", 30)
CALENDAR_LOOKAHEAD_MIN = _int("CALENDAR_LOOKAHEAD_MIN", 60 * 24)

GOOGLE_CREDENTIALS_FILE = _flag("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_TOKEN_FILE = _flag("GOOGLE_TOKEN_FILE", "token.json")

# ── Local backend ────────────────────────────────────────────────────────────
OLLAMA_HOST = _flag("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = _flag("OLLAMA_MODEL", "mistral")
WHISPER_MODEL = _flag("WHISPER_MODEL", "small")
VOICE_REFERENCE_WAV = _flag("VOICE_REFERENCE_WAV")

LISTEN_CHUNK_SEC = _float("LISTEN_CHUNK_SEC", 3.0)
# Consecutive quiet chunks before assuming the meeting is over.
MAX_SILENT_CHUNKS = _int("MAX_SILENT_CHUNKS", 40)
# Meet needs a moment after unmuting before it actually transmits; speaking
# immediately gets the start of the sentence cut off, or dropped entirely.
UNMUTE_SETTLE_SEC = _float("UNMUTE_SETTLE_SEC", 0.6)

CHROME_PROFILE_DIR = _flag("CHROME_PROFILE_DIR", os.path.expanduser("~/.config/google-chrome"))
CHROME_PROFILE_NAME = _flag("CHROME_PROFILE_NAME", "Default")
CHROME_BINARY = _flag("CHROME_BINARY", "/usr/bin/google-chrome")
HEADLESS = _flag("HEADLESS", "false").lower() in ("1", "true", "yes")

BOT_PERSONA = _flag(
    "BOT_PERSONA",
    "You are attending this Google Meet on behalf of the user. "
    "Be concise. Only respond when directly addressed or when you have something "
    "important to contribute. Keep responses under 3 sentences. "
    "If you don't need to say anything, reply with exactly: <SILENT>",
)

# ── Attendee backend ─────────────────────────────────────────────────────────
ATTENDEE_BASE_URL = _flag("ATTENDEE_BASE_URL", "https://app.attendee.dev/api/v1")
WEBHOOK_PUBLIC_URL = _flag("WEBHOOK_PUBLIC_URL").rstrip("/")
WEBHOOK_PORT = _int("WEBHOOK_PORT", 8765)
ATTENDEE_POLL_SEC = _int("ATTENDEE_POLL_SEC", 30)
