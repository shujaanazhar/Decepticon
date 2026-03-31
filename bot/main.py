"""
Decepticon Bot — main orchestrator.

Loop:
  1. Poll Google Calendar for upcoming meets
  2. Join the meet via Playwright
  3. Every N seconds: record audio → ASR → LLM → (maybe) TTS → play through virtual mic
  4. Leave when meeting ends or no one is talking
"""

import asyncio
import datetime
import os
import tempfile
import signal
import sys

from dotenv import load_dotenv
load_dotenv()

from gcalendar import get_upcoming_meets
from audio_pipeline import setup_virtual_audio, teardown_virtual_audio, play_audio_file, record_from_meet
from asr import transcribe
from llm import should_respond, reset_memory
from tts import synthesize
from meet_driver import MeetDriver

POLL_INTERVAL_SEC = 20       # How often to check calendar
LISTEN_CHUNK_SEC = float(os.getenv("LISTEN_CHUNK_SEC", "3.0"))
JOINED_MEETINGS = set()
# Join when meeting starts within this many seconds from now (past or future)
JOIN_WINDOW_SEC = 60


def handle_exit(sig, frame):
    print("\n[main] Shutting down...")
    teardown_virtual_audio()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)


async def attend_meeting(event: dict):
    print(f"\n[main] Joining: {event['title']} — {event['url']}")
    reset_memory()

    driver = MeetDriver(meet_url=event["url"], display_name="Decepticon")
    await driver.join()

    silence_count = 0
    max_silence = 40  # leave after 40 silent chunks (~120s) in a row

    try:
        while True:
            # Record a chunk of meeting audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                chunk_path = f.name

            record_from_meet(chunk_path, duration_sec=LISTEN_CHUNK_SEC)

            # Transcribe
            transcript = transcribe(chunk_path)
            os.unlink(chunk_path)

            # Filter Whisper hallucinations: single words or known artifacts
            if not transcript or len(transcript.split()) < 2 or "©" in transcript or transcript.strip().lower() in ("you", "you.", "thanks.", "thank you."):
                silence_count += 1
                print(f"[main] Silence/noise ({silence_count}/{max_silence}): {repr(transcript)}")
                if silence_count >= max_silence:
                    print("[main] Meeting seems over, leaving.")
                    break
                continue

            silence_count = 0
            print(f"[main] Heard: {transcript}")

            # Ask LLM if we should respond
            speak, response_text = should_respond(transcript)

            if speak and response_text:
                print(f"[main] Speaking: {response_text}")
                wav_path = synthesize(response_text)
                await driver.unmute()
                play_audio_file(wav_path)
                await driver.mute()
                os.unlink(wav_path)
            else:
                print("[main] LLM: staying silent.")

    except KeyboardInterrupt:
        pass
    finally:
        await driver.leave()


def parse_start_time(start_str: str) -> datetime.datetime:
    """Parse ISO start time to UTC-aware datetime."""
    from datetime import timezone
    import re
    # Handle offset like +05:00
    dt = datetime.datetime.fromisoformat(start_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def preload_models():
    """Load ASR and TTS models into VRAM at startup so there's no delay when joining."""
    print("[main] Pre-loading ASR model...")
    from asr import get_model
    get_model()

    print("[main] Pre-loading TTS model...")
    from tts import _load_model
    _load_model()

    print("[main] Models ready.")


async def main_loop():
    print("[main] Decepticon Bot starting...")
    setup_virtual_audio()
    preload_models()

    # scheduled_meetings: event_id -> asyncio.Task
    scheduled = {}

    async def schedule_meeting(event):
        from datetime import timezone
        start_dt = parse_start_time(event["start"])
        now = datetime.datetime.now(datetime.timezone.utc)
        wait_sec = (start_dt - now).total_seconds()

        join_early = float(os.getenv("JOIN_EARLY_SEC", "0"))
        wait_sec = wait_sec - join_early
        if wait_sec > 0:
            print(f"[main] Scheduled '{event['title']}' in {wait_sec:.0f}s")
            await asyncio.sleep(wait_sec)

        await attend_meeting(event)

    try:
        while True:
            # Look ahead 24h so we can schedule everything in advance
            meets = get_upcoming_meets(lookahead_minutes=60 * 24)
            for event in meets:
                eid = event["event_id"]
                if eid not in JOINED_MEETINGS and eid not in scheduled:
                    JOINED_MEETINGS.add(eid)
                    task = asyncio.create_task(schedule_meeting(event))
                    scheduled[eid] = task
                    print(f"[main] Queued: {event['title']} @ {event['start']}")

            await asyncio.sleep(POLL_INTERVAL_SEC)
    finally:
        for task in scheduled.values():
            task.cancel()
        teardown_virtual_audio()


if __name__ == "__main__":
    asyncio.run(main_loop())
