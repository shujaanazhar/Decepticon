"""
Pre-flight check. Only verifies what the configured backend actually needs, so
an attendee-only setup isn't told to install torch.

    .venv/bin/python check_deps.py
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))

import config  # noqa: E402

checks = []


def check(name, fn, fatal=True):
    try:
        fn()
        checks.append((name, True, "", fatal))
    except Exception as exc:
        checks.append((name, False, str(exc), fatal))


def importable(module):
    return lambda: __import__(module)


def command_works(*cmd):
    def run():
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        assert result.returncode == 0, f"{cmd[0]} exited {result.returncode}"

    return run


def ollama_running():
    import requests

    requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=3).raise_for_status()


def voice_reference_present():
    path = config.VOICE_REFERENCE_WAV
    assert path, "VOICE_REFERENCE_WAV not set — the bot will speak in a stock voice"
    assert os.path.exists(path), f"{path} not found"


def google_credentials_present():
    assert os.path.exists(config.GOOGLE_CREDENTIALS_FILE), (
        f"{config.GOOGLE_CREDENTIALS_FILE} not found — download it from Google Cloud Console"
    )


try:
    backend = config.resolve_backend()
except config.ConfigError as exc:
    print(f"\nConfiguration problem: {exc}")
    sys.exit(1)

print(f"\nChecking setup for: {config.describe_selection()}")

# Shared
check("python-dotenv", importable("dotenv"))
check("requests", importable("requests"))
check("google-api-python-client", importable("googleapiclient"))
check("credentials.json", google_credentials_present)

if backend == config.LOCAL:
    check("faster-whisper", importable("faster_whisper"))
    check("playwright", importable("playwright"))
    check("torch", importable("torch"))
    check("chatterbox-tts", importable("chatterbox"), fatal=False)
    check("sounddevice", importable("sounddevice"))
    check("soundfile", importable("soundfile"))
    check("pulsectl", importable("pulsectl"))
    check("pulseaudio (pactl)", command_works("pactl", "info"))
    check("ffmpeg", command_works("ffmpeg", "-version"))
    check("chrome", command_works(config.CHROME_BINARY, "--version"))
    check("ollama reachable", ollama_running)
    check("espeak-ng (TTS fallback)", command_works("espeak-ng", "--version"), fatal=False)
    check("voice reference wav", voice_reference_present, fatal=False)
else:
    check("flask", importable("flask"))
    check("ATTENDEE api key", lambda: (_ for _ in ()).throw(AssertionError("missing"))
          if not config.ATTENDEE_API_KEY else None)
    if not config.WEBHOOK_PUBLIC_URL:
        checks.append(
            ("WEBHOOK_PUBLIC_URL", False,
             "not set — transcripts arrive after the meeting instead of live", False)
        )

print()
blocking = 0
for name, ok, err, fatal in checks:
    if ok:
        mark = "✓"
    else:
        mark = "✗" if fatal else "!"
        blocking += 1 if fatal else 0
    print(f"  {mark} {name}" + (f"  → {err}" if not ok else ""))

print()
if blocking:
    print(f"{blocking} required check(s) failed. Fix those before running the bot.")
    sys.exit(1)

warnings = sum(1 for _, ok, _, fatal in checks if not ok and not fatal)
if warnings:
    print(f"Ready to run, with {warnings} warning(s) above — none of them blocking.")
else:
    print("All checks passed. You're good to go.")
