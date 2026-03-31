# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Decepticons** is an AI-powered Google Meet bot that autonomously joins scheduled meetings, transcribes speech, decides whether to respond using a local LLM, and speaks with a cloned voice.

## Environment Setup

All Python commands use the local venv:
```bash
.venv/bin/python <script>
```

Key environment variables (see `.env.example`):
- `OLLAMA_MODEL` / `OLLAMA_HOST` — local LLM (default: mistral at localhost:11434)
- `LUXTTS_PATH` — path to external LuxTTS repo
- `VOICE_REFERENCE_WAV` — WAV file for zero-shot voice cloning
- `WHISPER_MODEL` — Faster-Whisper model size (default: small)
- `CHROME_PROFILE_DIR` — existing Chrome profile with Google account signed in
- `BOT_PERSONA` — system prompt controlling bot behavior

## Running

```bash
# Validate all dependencies before running
.venv/bin/python check_deps.py

# Run the bot
.venv/bin/python bot/main.py
```

## Architecture

The bot runs a single `asyncio` event loop in `bot/main.py`:

1. **Startup**: preloads Whisper + LuxTTS models, sets up PulseAudio virtual devices
2. **Scheduling**: polls Google Calendar (24h lookahead) and schedules meeting joins
3. **Meeting loop**: for each meeting, Playwright automates Chrome to join the Meet URL, then loops:
   - Record audio chunk → transcribe (Faster-Whisper) → ask LLM if bot should respond → if yes: synthesize speech (LuxTTS) → unmute → play audio → mute

**Module responsibilities:**
- `main.py` — orchestrator, asyncio loop, model preloading, scheduling
- `meet_driver.py` — Playwright automation for joining/leaving Meet, mute control
- `gcalendar.py` — Google Calendar OAuth + event polling
- `audio_pipeline.py` — PulseAudio null sink + loopback virtual audio device setup
- `asr.py` — Faster-Whisper transcription
- `tts.py` — LuxTTS voice synthesis; falls back to `espeak-ng` if unavailable
- `llm.py` — Ollama HTTP API for LLM-based response decisions

**Audio pipeline**: PulseAudio virtual sink captures meeting audio; a loopback device injects synthesized speech back as a virtual microphone. GPU (CUDA) is used for both Whisper and LuxTTS inference.

**Google auth**: Uses OAuth installed app flow; `credentials.json` + `token.json` store the auth state. Chrome profile reuse avoids re-authenticating to Google Meet.
