"""
Decepticon — attends your Google Meet calls for you.

Watches Google Calendar, and when a meeting with a Meet link is about to
start, hands it to whichever backend is configured:

    local     runs everything on this machine and can speak in your voice
    attendee  uses the hosted Attendee service, listen-only

Which one runs is decided by config.resolve_backend(); by default it's local
unless an ATTENDEE key is present in .env.

Run:
    .venv/bin/python bot/main.py
"""

import asyncio
import datetime
import signal
import sys

import config
from backends import get_backend
from gcalendar import get_upcoming_meets


def parse_start_time(start_str: str) -> datetime.datetime:
    """Parse an ISO start time into an aware UTC datetime."""
    dt = datetime.datetime.fromisoformat(start_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class Orchestrator:
    def __init__(self, backend):
        self.backend = backend
        self.seen: set[str] = set()
        self.scheduled: dict[str, asyncio.Task] = {}

    async def run(self) -> None:
        await self.backend.startup()
        try:
            while True:
                await self._poll_calendar()
                await asyncio.sleep(config.POLL_INTERVAL_SEC)
        finally:
            await self._cancel_scheduled()
            await self.backend.shutdown()

    async def _poll_calendar(self) -> None:
        try:
            meets = await asyncio.to_thread(
                get_upcoming_meets, config.CALENDAR_LOOKAHEAD_MIN
            )
        except Exception as exc:
            print(f"[main] Calendar poll failed: {exc}")
            return

        for event in meets:
            event_id = event["event_id"]
            if event_id in self.seen:
                continue
            self.seen.add(event_id)
            self.scheduled[event_id] = asyncio.create_task(self._wait_then_attend(event))
            print(f"[main] Queued '{event['title']}' @ {event['start']}")

    async def _wait_then_attend(self, event: dict) -> None:
        try:
            start = parse_start_time(event["start"])
            now = datetime.datetime.now(datetime.timezone.utc)
            wait_sec = (start - now).total_seconds() - config.JOIN_EARLY_SEC

            if wait_sec > 0:
                print(f"[main] '{event['title']}' in {wait_sec:.0f}s")
                await asyncio.sleep(wait_sec)

            await self.backend.attend(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # One bad meeting shouldn't take the whole scheduler down.
            print(f"[main] '{event['title']}' failed: {exc}")
        finally:
            self.scheduled.pop(event["event_id"], None)

    async def _cancel_scheduled(self) -> None:
        tasks = [t for t in self.scheduled.values() if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.scheduled.clear()


async def main() -> int:
    try:
        backend = get_backend()
    except config.ConfigError as exc:
        print(f"[main] Configuration problem: {exc}")
        return 1

    print(f"[main] Decepticon starting — {config.describe_selection()}")
    if not backend.can_speak:
        print("[main] Note: this backend is listen-only. Use BOT_BACKEND=local to speak.")

    orchestrator = Orchestrator(backend)
    stopping = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stopping.set)

    runner = asyncio.create_task(orchestrator.run())
    stopper = asyncio.create_task(stopping.wait())

    done, _ = await asyncio.wait({runner, stopper}, return_when=asyncio.FIRST_COMPLETED)

    if stopper in done:
        print("\n[main] Shutting down...")
        runner.cancel()
        # Let run()'s finally block stop bots and tear down audio.
        await asyncio.gather(runner, return_exceptions=True)
    else:
        stopper.cancel()
        await asyncio.gather(stopper, return_exceptions=True)
        runner.result()  # re-raise if the orchestrator died

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
