"""Exercise MeetDriver's mic state machine against a fake Meet page."""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))

from meet_driver import MeetDriver


class FakeButton:
    """Mimics Meet's mic button: the label describes what a click would do."""

    def __init__(self, page):
        self.page = page

    async def wait_for(self, timeout=None):
        if self.page.button_missing:
            raise RuntimeError("no button")

    async def get_attribute(self, _name):
        if self.page.label_unreadable:
            return "Microphone"  # matches selector, but state is ambiguous
        return "Turn on microphone (ctrl + d)" if self.page.muted else "Turn off microphone (ctrl + d)"

    async def click(self, timeout=None):
        self.page.clicks += 1
        if self.page.clicks_that_fail > 0:
            self.page.clicks_that_fail -= 1
            raise RuntimeError("click intercepted")
        if self.page.clicks_that_noop > 0:
            self.page.clicks_that_noop -= 1
            return  # click landed but Meet ignored it
        self.page.muted = not self.page.muted


class FakeLocator:
    def __init__(self, page):
        self.first = FakeButton(page)


class FakePage:
    def __init__(self, muted=True, button_missing=False, label_unreadable=False,
                 clicks_that_fail=0, clicks_that_noop=0):
        self.muted = muted
        self.button_missing = button_missing
        self.label_unreadable = label_unreadable
        self.clicks_that_fail = clicks_that_fail
        self.clicks_that_noop = clicks_that_noop
        self.clicks = 0

    def locator(self, _sel):
        return FakeLocator(self)


def driver_with(page):
    d = MeetDriver.__new__(MeetDriver)
    d._page = page
    return d


async def check(name, page, coro_name, expect_ok, expect_muted):
    d = driver_with(page)
    ok = await getattr(d, coro_name)()
    passed = ok is expect_ok and page.muted is expect_muted
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}: returned {ok}, muted={page.muted}, clicks={page.clicks}")
    return passed


async def main():
    print("Mic state machine:")
    results = [
        await check("unmute from muted", FakePage(muted=True), "unmute", True, False),
        await check("unmute when already live", FakePage(muted=False), "unmute", True, False),
        await check("mute from live", FakePage(muted=False), "mute", True, True),
        await check("mute when already muted", FakePage(muted=True), "mute", True, True),
        await check("unmute, first click swallowed",
                    FakePage(muted=True, clicks_that_noop=1), "unmute", True, False),
        await check("unmute, first click raises",
                    FakePage(muted=True, clicks_that_fail=1), "unmute", True, False),
        await check("unmute, button absent",
                    FakePage(muted=True, button_missing=True), "unmute", False, True),
        await check("unmute, label unreadable",
                    FakePage(muted=True, label_unreadable=True), "unmute", False, True),
    ]

    print("\nspeak() sequencing:")
    order = []

    page = FakePage(muted=True)
    d = driver_with(page)

    def fake_play(path):
        order.append(("play", page.muted))

    ok = await d.speak(fake_play, "/tmp/x.wav")
    played_while_live = order and order[0][1] is False
    seq_ok = ok and played_while_live and page.muted is True
    print(f"  [{'PASS' if seq_ok else 'FAIL'}] played while unmuted={played_while_live}, "
          f"re-muted after={page.muted}, returned={ok}")
    results.append(seq_ok)

    # Never play into a mic that refused to unmute.
    page2 = FakePage(muted=True, button_missing=True)
    d2 = driver_with(page2)
    played = []
    ok2 = await d2.speak(lambda p: played.append(p), "/tmp/x.wav")
    skip_ok = ok2 is False and not played
    print(f"  [{'PASS' if skip_ok else 'FAIL'}] skipped playback when unmute failed "
          f"(returned={ok2}, played={len(played)})")
    results.append(skip_ok)

    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


sys.exit(asyncio.run(main()))
