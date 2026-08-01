# Contributing to Decepticon

A bot that joins meetings and talks touches a lot of fragile surfaces — Meet's
DOM, PulseAudio routing, WebRTC's noise gating. Most of what breaks here breaks
in the real world rather than in a type checker, so the bar for changes is
"I watched it work", not "it looks right".

## Before anything else: consent

This bot records and transcribes people. Whether that's legal, and whether it's
decent, depends on where you are and who's in the call. Tell participants there
is a bot in the room. Don't use this to record people who haven't agreed to it.

## Ways to help, roughly by value

1. **Make the local backend reliably speak.** This is the hard problem and the
   whole point of the project. See [Debugging the mic](#debugging-the-mic).
2. **Survive Meet's DOM changes.** The join and mic selectors will rot. More
   resilient targeting, or a way to detect breakage early, helps everyone.
3. **Reduce the reply latency.** Record → transcribe → LLM → synthesize → speak
   is a long chain, and a late answer is worse than none.
4. **A backend that speaks without a GPU.** A hosted-TTS local backend, or an
   Attendee variant wired to its Google TTS path, would widen who can run this.
5. **Portability.** The audio pipeline assumes PulseAudio/PipeWire on Linux.

## Never commit

`.env`, `credentials.json`, `token.json`, `my_voice.wav`, and **`transcripts/`**.
All are gitignored. Transcripts in particular are verbatim records of real
conversations with real names in them — they stay on the machine that made them.

```bash
git status --porcelain     # nothing from transcripts/ should ever appear
```

## Development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python check_deps.py     # checks only what your backend needs
```

For the local backend also install CUDA torch and the browser:

```bash
.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
.venv/bin/playwright install chromium
.venv/bin/python test_meet.py      # confirms Chrome + profile before anything else
```

Test against a meeting you created yourself, with nobody else in it.

## Tests

```bash
.venv/bin/python tests/run_all.py
```

Plain scripts, no pytest. Two things are covered and both are worth extending:
the mic state machine (`MeetDriver` with a fake page — no browser launched) and
the orchestrator (any `MeetingBackend` can be swapped in). Anything you can put
behind a fake, please do; the parts that need a live meeting are painful enough
already.

## Architecture

`bot/main.py` polls the calendar and schedules meetings. It knows nothing about
how one gets attended — that lives behind `backends/base.py::MeetingBackend`,
which is three methods. A new backend is a module in `bot/backends/` plus a
branch in `get_backend()`; `main.py` shouldn't change.

Two rules that aren't obvious:

- **Config comes from `bot/config.py`**, never `os.getenv` at a call site. It's
  the only module that calls `load_dotenv()`.
- **Backend imports stay lazy.** Someone running attendee-only must not need
  torch or Playwright. Don't hoist those imports to module scope.

## Debugging the mic

If the bot joins but stays silent, the logs narrate it. `[meet] Mic live.` means
unmuting worked; `Mic still not live` means a click was swallowed; `Skipping
speech — mic never unmuted` means it refused to talk into a dead mic.

Two things have caused this before, both documented in `CLAUDE.md`:

- Meet labels the mic button by **what a click would do**. `"Turn on
  microphone"` means it's currently *muted*. Reading that backwards is why an
  earlier version sat silent through entire meetings.
- `[aria-label*="microphone"]` matches the mute **toggle**, not a device menu.
  Clicking it to "pick a device" mutes the bot.

Run with `HEADLESS=false` and read the screenshots in `/tmp/meet_debug*.png`.

## Pull requests

- One logical change per PR.
- Say what you tested on: distro, GPU, whether it actually spoke in a real call.
- Note new dependencies and which backend needs them.

## Reporting a security issue

Don't open a public issue. Email shujaan.azhar@gmail.com instead.
