"""Quick dependency check before running the bot."""

import sys

checks = []

def check(name, fn):
    try:
        fn()
        checks.append((name, True, ""))
    except Exception as e:
        checks.append((name, False, str(e)))

check("faster-whisper", lambda: __import__("faster_whisper"))
check("playwright", lambda: __import__("playwright"))
check("google-api-python-client", lambda: __import__("googleapiclient"))
check("sounddevice", lambda: __import__("sounddevice"))
check("soundfile", lambda: __import__("soundfile"))
check("pulsectl", lambda: __import__("pulsectl"))
check("requests", lambda: __import__("requests"))
check("dotenv", lambda: __import__("dotenv"))

# Check Ollama is running
def check_ollama():
    import requests, os
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    r = requests.get(f"{host}/api/tags", timeout=3)
    r.raise_for_status()

check("ollama (running)", check_ollama)

# Check PulseAudio
def check_pulse():
    import subprocess
    r = subprocess.run(["pactl", "info"], capture_output=True, timeout=3)
    assert r.returncode == 0

check("pulseaudio", check_pulse)

# Check espeak fallback
def check_espeak():
    import subprocess
    r = subprocess.run(["espeak-ng", "--version"], capture_output=True, timeout=3)
    assert r.returncode == 0

check("espeak-ng (TTS fallback)", check_espeak)

print("\nDependency check:")
all_ok = True
for name, ok, err in checks:
    status = "✓" if ok else "✗"
    print(f"  {status} {name}" + (f"  → {err}" if not ok else ""))
    if not ok:
        all_ok = False

print()
if all_ok:
    print("All checks passed. You're good to go!")
else:
    print("Some checks failed. Fix the issues above before running the bot.")
    sys.exit(1)
