"""
Attendee backend — the hosted service joins the meeting for us.

Listen-only. Attendee can emit speech, but only through Google Cloud TTS with
a stock voice, which needs separate credentials and defeats the point of the
voice clone. If you want the bot to talk, use the local backend.
"""

import asyncio

import attendee_client
import config
import webhook_server
from transcripts import Transcript, stamp_from_ms

from .base import MeetingBackend

ENDED_STATES = {"ended", "fatal_error", "post_processing_complete"}


class AttendeeBackend(MeetingBackend):
    name = "attendee"
    can_speak = False

    def __init__(self):
        self._webhook_url = None
        self._active: dict[str, str] = {}  # event_id -> bot_id

    async def startup(self) -> None:
        if config.WEBHOOK_PUBLIC_URL:
            self._webhook_url = f"{config.WEBHOOK_PUBLIC_URL}/webhook"
            webhook_server.start_in_background(config.WEBHOOK_PORT)
            print(f"[attendee] Webhook listening on :{config.WEBHOOK_PORT} → {self._webhook_url}")
        else:
            print("[attendee] No WEBHOOK_PUBLIC_URL — transcripts fetched after each meeting.")
            print("[attendee] For live transcripts: ngrok http "
                  f"{config.WEBHOOK_PORT}, then set WEBHOOK_PUBLIC_URL.")

    async def attend(self, event: dict) -> None:
        title, url, event_id = event["title"], event["url"], event["event_id"]

        print(f"[attendee] Sending bot to '{title}'")
        try:
            bot = await asyncio.to_thread(
                attendee_client.create_bot,
                meeting_url=url,
                bot_name=config.BOT_NAME,
                webhook_url=self._webhook_url,
            )
        except Exception as exc:
            print(f"[attendee] Could not create bot: {exc}")
            return

        bot_id = bot["id"]
        self._active[event_id] = bot_id
        print(f"[attendee] Bot {bot_id} joining '{title}'")

        if self._webhook_url:
            webhook_server.register_session(bot_id, title)

        try:
            final_state = await self._wait_for_end(bot_id, title)
        finally:
            self._active.pop(event_id, None)

        if self._webhook_url:
            webhook_server.close_session(bot_id, final_state)
        else:
            await asyncio.to_thread(self._save_transcript, bot_id, title)

    async def _wait_for_end(self, bot_id: str, title: str) -> str:
        """Poll bot state until the meeting finishes. Returns the final state."""
        while True:
            await asyncio.sleep(config.ATTENDEE_POLL_SEC)
            try:
                state = (await asyncio.to_thread(attendee_client.get_bot, bot_id)).get(
                    "state", "unknown"
                )
            except Exception as exc:
                print(f"[attendee] State poll failed for {bot_id}: {exc}")
                continue

            print(f"[attendee] {bot_id} → {state}")
            if state in ENDED_STATES:
                print(f"[attendee] '{title}' ended ({state})")
                return state

    def _save_transcript(self, bot_id: str, title: str) -> None:
        """Fetch the whole transcript at once — the no-webhook path."""
        transcript = Transcript(title, bot_id, backend="attendee")
        try:
            for utterance in attendee_client.get_transcript(bot_id):
                transcript.line(
                    speaker=utterance.get("speaker_name", "Unknown"),
                    text=utterance.get("transcription", {}).get("transcript", ""),
                    timestamp=stamp_from_ms(utterance.get("timestamp_ms", 0)),
                )
            transcript.close("fetched after meeting")
        except Exception as exc:
            transcript.close(f"fetch failed: {exc}")
            print(f"[attendee] Could not fetch transcript for {bot_id}: {exc}")

    async def shutdown(self) -> None:
        for event_id, bot_id in list(self._active.items()):
            try:
                await asyncio.to_thread(attendee_client.stop_bot, bot_id)
                print(f"[attendee] Stopped bot {bot_id}")
            except Exception as exc:
                print(f"[attendee] Could not stop bot {bot_id}: {exc}")
            self._active.pop(event_id, None)
