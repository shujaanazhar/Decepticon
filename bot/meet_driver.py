"""
Google Meet automation via Playwright.

Joins the meeting, keeps the mic muted while listening, and unmutes only long
enough to say something.

Mic handling is deliberately paranoid. Meet exposes one button that both
reports and toggles mic state through its aria-label ("Turn on microphone"
when muted, "Turn off microphone" when live), and the earlier version of this
file assumed a click always landed. It did not, and the bot sat silent through
whole meetings. Every state change here is verified by re-reading the label.
"""

import asyncio

from playwright.async_api import Browser, Page, async_playwright

import config

# Meet labels the button by what clicking it would DO, not by current state.
_MUTED_HINT = "turn on microphone"
_LIVE_HINT = "turn off microphone"

_MIC_SELECTOR = '[aria-label*="microphone" i][role="button"], button[aria-label*="microphone" i]'


class MeetDriver:
    def __init__(self, meet_url: str, display_name: str = None):
        self.meet_url = meet_url
        self.display_name = display_name or config.BOT_NAME
        self._playwright = None
        self._browser: Browser = None
        self._page: Page = None

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def join(self):
        self._playwright = await async_playwright().start()

        context = await self._playwright.chromium.launch_persistent_context(
            config.CHROME_PROFILE_DIR,
            executable_path=config.CHROME_BINARY,
            headless=config.HEADLESS,
            args=[
                f"--profile-directory={config.CHROME_PROFILE_NAME}",
                "--use-fake-ui-for-media-stream",  # auto-accept mic/camera prompts
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--alsa-output-device=pulse",
                "--alsa-input-device=pulse",
                # Stop WebRTC from treating synthesized speech as noise and
                # gating it out entirely.
                "--disable-features=WebRtcHWDecoding,WebRtcHWEncoding,"
                "WebRtcAecRefinedAdaptiveFilter,WebRtcHybridAgc",
                "--force-fieldtrials=WebRTC-Audio-Red-For-Opus/Disabled/"
                "WebRTC-Audio-SendSideBwe/Disabled/",
                "--disable-audio-processing",
                "--disable-webrtc-apm-in-audio-service",
            ],
            permissions=["camera", "microphone"],
        )
        self._browser = context

        self._page = await context.new_page()
        print(f"[meet] Opening {self.meet_url}")
        await self._page.goto(self.meet_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        await self._page.screenshot(path="/tmp/meet_debug.png")

        await self._try_enter_name()
        await self._turn_off_camera()
        await self._click_join()

        # Settle, then take stock of the mic. Do NOT touch the device dropdown:
        # Chrome already defaults to the virtual mic because audio_pipeline set
        # it as the PulseAudio default source before this browser launched.
        await asyncio.sleep(3)
        state = await self._mic_state()
        print(f"[meet] Joined. Mic is {state or 'in an unknown state'}.")
        await self.mute()

    async def leave(self):
        try:
            await self._page.get_by_role("button", name="Leave call").click(timeout=3000)
        except Exception:
            pass
        await asyncio.sleep(1)
        for closer in (self._page.close, self._browser.close):
            try:
                await closer()
            except Exception:
                pass
        try:
            await self._playwright.stop()
        except Exception:
            pass
        print("[meet] Left meeting.")

    # ── pre-join ─────────────────────────────────────────────────────────────

    async def _try_enter_name(self):
        try:
            await self._page.get_by_role("button", name="Got it").click(timeout=3000)
        except Exception:
            pass
        try:
            name_input = self._page.get_by_placeholder("Your name")
            await name_input.wait_for(timeout=5000)
            await name_input.fill(self.display_name)
        except Exception:
            pass  # already signed in

    async def _turn_off_camera(self):
        try:
            cam = self._page.locator('button[aria-label*="camera" i]').first
            label = (await cam.get_attribute("aria-label") or "").lower()
            if "turn off camera" in label:
                await cam.click(timeout=3000)
                print("[meet] Camera off.")
        except Exception:
            pass

    async def _click_join(self):
        page = self._page
        candidates = [
            ("role", "Join now"),
            ("role", "Ask to join"),
            ("role", "Join"),
            ("role", "Continue without microphone"),
            ("attr", '[data-idom-class*="join" i]'),
            ("text", "Join now"),
            ("text", "Ask to join"),
        ]

        for attempt in range(3):
            for kind, value in candidates:
                try:
                    if kind == "role":
                        await page.get_by_role("button", name=value).click(timeout=3000)
                    elif kind == "attr":
                        await page.locator(value).first.click(timeout=3000)
                    else:
                        await page.get_by_text(value, exact=True).click(timeout=2000)
                    print(f"[meet] Clicked '{value}'")
                    await asyncio.sleep(3)
                    await page.screenshot(path="/tmp/meet_after_join.png")
                    return
                except Exception:
                    continue
            print(f"[meet] Join button not found (attempt {attempt + 1}/3)")
            await asyncio.sleep(3)
            await page.screenshot(path=f"/tmp/meet_debug_{attempt + 1}.png")

        print("[meet] WARNING: never found a join button — see /tmp/meet_debug_*.png")

    # ── microphone ───────────────────────────────────────────────────────────

    async def _mic_button(self):
        """The mic toggle, or None if the DOM doesn't show one."""
        try:
            button = self._page.locator(_MIC_SELECTOR).first
            await button.wait_for(timeout=3000)
            return button
        except Exception:
            return None

    async def _mic_state(self) -> str | None:
        """'muted', 'live', or None when the label can't be read."""
        button = await self._mic_button()
        if button is None:
            return None
        label = (await button.get_attribute("aria-label") or "").lower()
        if _MUTED_HINT in label:
            return "muted"
        if _LIVE_HINT in label:
            return "live"
        return None

    async def _set_mic(self, want_live: bool, retries: int = 3) -> bool:
        """
        Drive the mic to the requested state, verifying after each click.

        Returns True once the state matches, False if it never took.
        """
        target = "live" if want_live else "muted"

        for attempt in range(retries):
            state = await self._mic_state()

            if state == target:
                return True

            if state is None:
                # Label unreadable — the page may still be settling.
                await asyncio.sleep(0.5)
                continue

            button = await self._mic_button()
            if button is None:
                await asyncio.sleep(0.5)
                continue

            try:
                await button.click(timeout=3000)
            except Exception as exc:
                print(f"[meet] Mic click failed: {exc}")

            # Meet updates the label asynchronously; give it a beat before
            # believing the result.
            await asyncio.sleep(0.4)
            if await self._mic_state() == target:
                print(f"[meet] Mic {target}.")
                return True

            print(f"[meet] Mic still not {target} (attempt {attempt + 1}/{retries})")

        print(f"[meet] WARNING: could not set mic to {target}.")
        return False

    async def mute(self) -> bool:
        return await self._set_mic(want_live=False)

    async def unmute(self) -> bool:
        return await self._set_mic(want_live=True)

    async def speak(self, play_fn, wav_path: str) -> bool:
        """
        Unmute, play `wav_path` through the virtual mic, mute again.

        `play_fn` is a blocking callable, run off the event loop. Returns False
        if the mic never went live — the audio is not played in that case,
        because playing into a muted mic just wastes the utterance.
        """
        if not await self.unmute():
            print("[meet] Skipping speech — mic never unmuted.")
            return False

        # WebRTC takes a moment to actually start sending after unmute. Without
        # this the opening words are clipped, and short replies vanish entirely.
        await asyncio.sleep(config.UNMUTE_SETTLE_SEC)

        try:
            await asyncio.to_thread(play_fn, wav_path)
        finally:
            # Let the tail of the audio flush before cutting the mic.
            await asyncio.sleep(0.3)
            await self.mute()

        return True

    # ── misc ─────────────────────────────────────────────────────────────────

    async def get_captions_text(self) -> str:
        """Read live captions if they're enabled."""
        try:
            captions = self._page.locator('[class*="caption" i]')
            return " ".join(await captions.all_inner_texts()).strip()
        except Exception:
            return ""
