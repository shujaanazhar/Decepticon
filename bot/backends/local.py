"""
Local backend — everything runs on this machine.

Playwright drives a real Chrome into the meeting, PulseAudio virtual devices
carry audio both ways, Whisper transcribes, Ollama decides whether to speak,
and Chatterbox says it in the cloned voice.

Free and private, but it needs a GPU, a PulseAudio/PipeWire session, and a
Chrome profile already signed in to Google.
"""

import asyncio
import os
import tempfile

import config
from transcripts import Transcript

from .base import MeetingBackend

# Whisper invents these on silence; treating them as speech makes the bot
# babble into an empty room.
_HALLUCINATIONS = {"you", "you.", "thanks.", "thank you.", "bye.", "."}


def _is_noise(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip().lower()
    if stripped in _HALLUCINATIONS or "©" in text:
        return True
    return len(stripped.split()) < 2


class LocalBackend(MeetingBackend):
    name = "local"
    can_speak = True

    def __init__(self):
        self._audio_ready = False

    async def startup(self) -> None:
        from audio_pipeline import setup_virtual_audio

        setup_virtual_audio()
        self._audio_ready = True

        # Pull both models into VRAM now so the first reply isn't 30s late.
        print("[local] Pre-loading Whisper...")
        from asr import get_model

        await asyncio.to_thread(get_model)

        print("[local] Pre-loading TTS...")
        from tts import load_model

        await asyncio.to_thread(load_model)

        print("[local] Models ready.")

    async def attend(self, event: dict) -> None:
        from audio_pipeline import play_audio_file, record_from_meet
        from asr import transcribe
        from llm import reset_memory, should_respond
        from meet_driver import MeetDriver
        from tts import synthesize

        title, url = event["title"], event["url"]
        print(f"[local] Joining '{title}' — {url}")
        reset_memory()

        transcript = Transcript(title, event["event_id"], backend="local")
        driver = MeetDriver(meet_url=url, display_name=config.BOT_NAME)
        await driver.join()

        silent_chunks = 0
        try:
            while True:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                    chunk_path = fh.name

                await asyncio.to_thread(
                    record_from_meet, chunk_path, config.LISTEN_CHUNK_SEC
                )
                heard = await asyncio.to_thread(transcribe, chunk_path)
                os.unlink(chunk_path)

                if _is_noise(heard):
                    silent_chunks += 1
                    if silent_chunks >= config.MAX_SILENT_CHUNKS:
                        print("[local] Nothing said for a while — leaving.")
                        break
                    continue

                silent_chunks = 0
                print(f"[local] Heard: {heard}")
                transcript.line("Meeting", heard)

                speak, reply = await asyncio.to_thread(should_respond, heard)
                if not (speak and reply):
                    continue

                print(f"[local] Saying: {reply}")
                wav_path = await asyncio.to_thread(synthesize, reply)
                if not wav_path:
                    print("[local] TTS produced nothing — staying quiet.")
                    continue

                try:
                    await driver.speak(play_audio_file, wav_path)
                    transcript.line(config.BOT_NAME, reply)
                finally:
                    if os.path.exists(wav_path):
                        os.unlink(wav_path)

        except asyncio.CancelledError:
            raise
        finally:
            transcript.close()
            await driver.leave()

    async def shutdown(self) -> None:
        if not self._audio_ready:
            return
        from audio_pipeline import teardown_virtual_audio

        teardown_virtual_audio()
        self._audio_ready = False
