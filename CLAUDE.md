# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

**Decepticon** attends Google Meet calls from the user's calendar. It has two
interchangeable backends and picks one at startup:

- **local** — Playwright drives Chrome, Faster-Whisper transcribes, Ollama
  decides whether to speak, Chatterbox synthesizes the reply in a cloned voice.
  This is the only backend that can talk.
- **attendee** — the hosted Attendee service joins instead and posts transcripts
  to a webhook. Listen-only by design.

Selection lives in `bot/config.py::resolve_backend()`: `BOT_BACKEND=auto` (the
default) picks attendee when `ATTENDEE` is set in `.env`, otherwise local.

## Commands

```bash
.venv/bin/python check_deps.py    # backend-aware pre-flight
.venv/bin/python bot/main.py      # run
```

All Python goes through `.venv/bin/python`.

## Architecture

`bot/main.py` owns the loop that polls Google Calendar, schedules each meeting,
and dispatches it. It knows nothing about *how* a meeting gets attended — that
is entirely behind `backends/base.py::MeetingBackend`, which is three methods:
`startup()`, `attend(event)`, `shutdown()`.

Adding a backend means adding a module under `bot/backends/` and a branch in
`backends/__init__.py::get_backend()`. Nothing in `main.py` should change.

**Imports are lazy on purpose.** `get_backend()` imports the chosen backend only,
and `local.py` imports torch/Whisper/Playwright inside its methods rather than at
module scope. Someone running attendee-only must not need the local stack
installed. Don't hoist those imports to the top of a module.

## Conventions

- **Config comes from `bot/config.py`, never `os.getenv` at a call site.** It is
  the only module that calls `load_dotenv()`.
- Blocking work (recording, transcription, synthesis, playback, HTTP) belongs in
  `asyncio.to_thread` — the orchestrator schedules concurrent meetings and a
  blocking call stalls all of them.
- Both backends write transcripts through `transcripts.Transcript`, appending
  per utterance so a crash mid-meeting still leaves a usable file.
- Never commit `.env`, `credentials.json`, `token.json`, or `my_voice.wav`.

## Mic handling — read before touching `meet_driver.py`

Meet labels the mic button by **what a click would do**, not by current state:
`"Turn on microphone"` means it is currently *muted*. Getting this backwards is
why an earlier version sat silent through entire meetings.

Two rules, both learned the hard way:

1. **Verify every state change.** `_set_mic()` clicks, re-reads the label, and
   retries. Clicks get swallowed by overlays and animations; assuming one landed
   is what broke it before.
2. **Never click `[aria-label*="microphone"]` to open a device menu.** That
   selector matches the mute *toggle*. The old pre-join code did this and muted
   the bot on the way in. Chrome already defaults to the virtual mic because
   `audio_pipeline.setup_virtual_audio()` sets it as the PulseAudio default
   source before the browser launches — there is nothing to select.

`speak()` is the only sanctioned way to make sound: it unmutes, verifies,
waits `UNMUTE_SETTLE_SEC` for WebRTC to start transmitting, plays, then re-mutes.
Skipping the settle clips the opening words and can drop short replies entirely.
If unmuting fails it refuses to play rather than talking into a dead mic.

## Testing

There is no test suite in the repo. The mic state machine and the orchestrator
are both testable with fakes — `MeetDriver` only needs `_page` set, and
`Orchestrator` takes any `MeetingBackend`. Prefer that over reasoning about
Playwright behaviour in the abstract.
