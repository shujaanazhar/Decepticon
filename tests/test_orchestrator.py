"""Drive the orchestrator with a fake backend and fake calendar."""

import asyncio
from pathlib import Path
import datetime
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))

import main as orchestrator_mod
from backends.base import MeetingBackend

results = []


class FakeBackend(MeetingBackend):
    name = "fake"
    can_speak = True

    def __init__(self):
        self.attended = []
        self.started = False
        self.stopped = False

    async def startup(self):
        self.started = True

    async def attend(self, event):
        self.attended.append(event["title"])

    async def shutdown(self):
        self.stopped = True


class ExplodingBackend(FakeBackend):
    async def attend(self, event):
        self.attended.append(event["title"])
        raise RuntimeError("meeting blew up")


def soon(seconds):
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
    return dt.isoformat()


def event(eid, title, start):
    return {"event_id": eid, "title": title, "url": f"https://meet.google.com/{eid}", "start": start}


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    results.append(ok)


async def run_briefly(orch, seconds=0.6):
    task = asyncio.create_task(orch.run())
    await asyncio.sleep(seconds)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def main():
    cfg = orchestrator_mod.config
    cfg.POLL_INTERVAL_SEC = 0.1
    cfg.JOIN_EARLY_SEC = 0
    calls = {"n": 0}

    print("Orchestrator:")

    # A meeting already due is attended immediately; duplicates are ignored.
    feed = [event("a", "Standup", soon(-5)), event("a", "Standup", soon(-5))]
    orchestrator_mod.get_upcoming_meets = lambda _m: feed
    backend = FakeBackend()
    await run_briefly(orchestrator_mod.Orchestrator(backend))
    check("attends a due meeting", backend.attended == ["Standup"], f"attended={backend.attended}")
    check("startup and shutdown both run", backend.started and backend.stopped)

    # A future meeting is queued but not attended yet.
    orchestrator_mod.get_upcoming_meets = lambda _m: [event("b", "Later", soon(3600))]
    backend = FakeBackend()
    await run_briefly(orchestrator_mod.Orchestrator(backend))
    check("waits for a future meeting", backend.attended == [], f"attended={backend.attended}")

    # A calendar error must not kill the loop.
    def boom(_m):
        calls["n"] += 1
        raise RuntimeError("calendar down")

    orchestrator_mod.get_upcoming_meets = boom
    backend = FakeBackend()
    await run_briefly(orchestrator_mod.Orchestrator(backend))
    check("survives calendar errors", calls["n"] > 1, f"polled {calls['n']}x despite failures")

    # One failing meeting must not stop later ones.
    orchestrator_mod.get_upcoming_meets = lambda _m: [
        event("c", "Bad", soon(-5)),
        event("d", "Good", soon(-5)),
    ]
    backend = ExplodingBackend()
    await run_briefly(orchestrator_mod.Orchestrator(backend))
    check("one bad meeting doesn't stop the rest",
          set(backend.attended) == {"Bad", "Good"}, f"attended={backend.attended}")
    check("shutdown still runs after a failure", backend.stopped)

    print("\nNoise filter:")
    from backends.local import _is_noise

    cases = [
        ("", True), ("   ", True), ("you", True), ("You.", True), ("thanks.", True),
        ("© transcribed by someone", True), ("okay", True),
        ("what do you think about the roadmap", False), ("yes I agree", False),
    ]
    for text, expected in cases:
        got = _is_noise(text)
        check(f"_is_noise({text!r}) == {expected}", got == expected)

    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


sys.exit(asyncio.run(main()))
