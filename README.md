# Decepticon

A bot that attends your Google Meet calls. It watches your calendar, joins when
a meeting starts, transcribes what's said — and, if you run it locally, decides
when to speak and answers in a clone of your own voice.

## Two backends, one switch

| | **local** | **attendee** |
|---|---|---|
| Joins via | Chrome, driven by Playwright | hosted [Attendee](https://attendee.dev) service |
| Transcribes with | Faster-Whisper, on your GPU | Attendee, streamed to a webhook |
| Decides what to say | Ollama | — |
| **Speaks** | **yes, in your cloned voice** | **no, listen-only** |
| Costs | nothing | free for 5 hours, then paid |
| Needs | GPU, PulseAudio, signed-in Chrome | an API key |

**You don't pick this by editing code.** Put an `ATTENDEE` key in `.env` and the
attendee backend is used; leave it blank and everything runs locally:

```bash
BOT_BACKEND=auto      # the default — decides based on whether ATTENDEE is set
BOT_BACKEND=local     # force local, even with a key present
BOT_BACKEND=attendee  # force attendee, errors if no key
```

On startup the bot prints which one it chose and why, and warns you if the
chosen backend can't speak.

Attendee *can* emit speech, but only through Google Cloud TTS with a stock
voice — separate credentials, and not your voice. That's why the attendee
backend here stays listen-only. If you want the bot to talk, run local.

## Setup

```bash
git clone https://github.com/shujaanazhar/Decepticon.git
cd Decepticon
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Both backends need Google Calendar access: create a project in the
[Google Cloud Console](https://console.cloud.google.com/), enable the Calendar
API, and download the OAuth client as `credentials.json` into the project root.
The first run opens a browser to authorize and writes `token.json`.

**For the local backend**, additionally:

```bash
.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
.venv/bin/playwright install chromium
```

Then set in `.env`:

- `CHROME_PROFILE_DIR` — a Chrome profile already signed in to Google
- `VOICE_REFERENCE_WAV` — ~10s of clean speech; this is the voice it clones
- `OLLAMA_MODEL` — whichever model you've pulled (default `mistral`)

**For the attendee backend**, set `ATTENDEE` to your key from
[app.attendee.dev](https://app.attendee.dev). Optionally run `ngrok http 8765`
and set `WEBHOOK_PUBLIC_URL` for live transcripts; without it, transcripts are
fetched once the meeting ends.

## Run

```bash
.venv/bin/python check_deps.py    # checks only what your backend needs
.venv/bin/python bot/main.py
```

It polls your calendar, queues every meeting with a Meet link, and joins each
one `JOIN_EARLY_SEC` before it starts. Transcripts land in `transcripts/`, one
file per meeting, written as the meeting happens so a crash doesn't lose them.

## How the local backend works

```
Google Calendar → meeting due
       ↓
Playwright → Chrome joins the Meet, mic muted
       ↓
parec ← meet_capture sink → Faster-Whisper → text
       ↓
Ollama → speak, or stay silent?
       ↓
Chatterbox → WAV in your voice
       ↓
unmute → verify → settle → paplay → tts_sink → virtual mic → Meet → re-mute
```

The mic is muted whenever the bot isn't actively speaking.

### Audio devices

Three PulseAudio nodes, no loopbacks and therefore no feedback:

- `meet_capture` — Chrome's output; the bot records from its monitor
- `decepticon_tts_sink` — synthesized speech plays here
- `decepticon_virtual_mic` — remaps that sink's monitor into a microphone Chrome
  will accept, and is made the default source *before* Chrome launches so it
  gets picked up without touching Meet's device menu

## Layout

```
bot/
  main.py              orchestrator — calendar polling, scheduling, dispatch
  config.py            all settings and the backend decision
  transcripts.py       per-meeting transcript files (both backends)
  gcalendar.py         Google Calendar OAuth + event polling
  backends/
    base.py            the interface a backend implements
    local.py           Playwright + Whisper + Ollama + Chatterbox
    attendee.py        Attendee API + webhook
  meet_driver.py       Chrome automation and mic control   (local)
  audio_pipeline.py    PulseAudio virtual devices          (local)
  asr.py               Faster-Whisper                      (local)
  llm.py               Ollama                              (local)
  tts.py               Chatterbox, espeak-ng fallback      (local)
  attendee_client.py   Attendee REST client            (attendee)
  webhook_server.py    Flask transcript receiver       (attendee)
```

Backend modules are imported only when selected, so an attendee-only setup
never needs torch, Whisper or Playwright installed.

## Known limits

- Linux only — the audio pipeline assumes PulseAudio/PipeWire.
- The local backend needs a GPU; Whisper and Chatterbox both want VRAM.
- Meet's DOM changes without warning. If joining breaks, check the screenshots
  the driver leaves in `/tmp/meet_debug*.png`.
- No tests around the browser automation itself.
