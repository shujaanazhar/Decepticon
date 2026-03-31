# Decepticon

An AI-powered Google Meet bot that autonomously joins scheduled meetings, listens, and speaks using a cloned voice.

## What it does

- Joins Google Meet meetings automatically from your Google Calendar
- Transcribes speech using Faster-Whisper (runs locally on GPU)
- Decides when to respond using a local LLM (Ollama/Mistral)
- Speaks back using Chatterbox TTS with zero-shot voice cloning
- Uses virtual PulseAudio devices — no physical mic/speaker needed

## Requirements

- Linux with PipeWire/PulseAudio
- NVIDIA GPU (CUDA) for Whisper + Chatterbox
- Google Chrome installed
- Ollama running locally with a model (default: mistral)
- Python 3.10+

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/shujaanazhar/Decepticon.git
cd Decepticon
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Google Calendar credentials

- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a project, enable Google Calendar API
- Download OAuth credentials as `credentials.json` and place in project root
- On first run, a browser will open to authorize — this creates `token.json`

### 3. Chrome profile

Create a dedicated Chrome profile signed into your Google account:

```bash
google-chrome --profile-directory=Default --user-data-dir=/home/$USER/.config/google-chrome-bot
```

Sign into Google in that window, then close it.

### 4. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` and set:
- `CHROME_PROFILE_DIR` — path to your bot Chrome profile
- `VOICE_REFERENCE_WAV` — path to a ~10s WAV of your voice for cloning
- `OLLAMA_MODEL` — Ollama model name (default: mistral)
- `BOT_PERSONA` — system prompt for the bot's behavior

### 5. Validate setup

```bash
.venv/bin/python check_deps.py
```

### 6. Run

```bash
DISPLAY=:1 .venv/bin/python bot/main.py
```

The bot will poll your calendar every 20 seconds and join any upcoming meetings automatically.

## Architecture

```
Google Calendar → scheduled meeting detected
       ↓
Playwright (Chrome) → joins Meet URL
       ↓
parec → meet_capture sink → Faster-Whisper ASR → transcript
       ↓
Ollama LLM → decides to respond or stay silent
       ↓
Chatterbox TTS → synthesized WAV → ffmpeg volume boost
       ↓
paplay → decepticon_tts_sink → decepticon_virtual_mic → Chrome mic input → Meet
```

## Audio pipeline

Uses PulseAudio null sinks and a remap-source virtual mic — no loopbacks, no feedback:

- `meet_capture` — Chrome's audio output routes here; bot records from its monitor
- `decepticon_tts_sink` — TTS audio plays here at 200% volume
- `decepticon_virtual_mic` — exposes TTS sink monitor as Chrome's microphone input

## Modules

| File | Purpose |
|------|---------|
| `bot/main.py` | Orchestrator — calendar polling, meeting loop |
| `bot/meet_driver.py` | Playwright automation for joining/leaving Meet |
| `bot/audio_pipeline.py` | PulseAudio virtual device setup |
| `bot/asr.py` | Faster-Whisper transcription |
| `bot/tts.py` | Chatterbox TTS voice synthesis |
| `bot/llm.py` | Ollama LLM response decisions |
| `bot/gcalendar.py` | Google Calendar OAuth + event polling |
