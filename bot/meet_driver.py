"""
Google Meet automation via Playwright.

Joins the meeting, grants mic/camera permissions (using virtual devices),
and exposes methods to mute/unmute and leave.
"""

import asyncio
import os
from playwright.async_api import async_playwright, Browser, Page

VIRTUAL_SOURCE_NAME = os.getenv("PULSE_VIRTUAL_SOURCE", "decepticon_source")


class MeetDriver:
    def __init__(self, meet_url: str, display_name: str = "Decepticon"):
        self.meet_url = meet_url
        self.display_name = display_name
        self._playwright = None
        self._browser: Browser = None
        self._page: Page = None

    async def join(self):
        self._playwright = await async_playwright().start()

        # Use the existing signed-in Chrome profile (already signed into Google)
        user_data_dir = os.getenv(
            "CHROME_PROFILE_DIR",
            "/home/user/.config/google-chrome"
        )
        profile_dir = os.getenv("CHROME_PROFILE_NAME", "Default")
        chrome_bin = os.getenv("CHROME_BINARY", "/usr/bin/google-chrome")

        context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir,
            executable_path=chrome_bin,
            headless=False,
            args=[
                f"--profile-directory={profile_dir}",
                "--use-fake-ui-for-media-stream",  # auto-accept mic/camera permission prompts
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--alsa-output-device=pulse",
                "--alsa-input-device=pulse",
                # Disable WebRTC audio processing so Meet doesn't filter/suppress TTS voice
                "--disable-features=WebRtcHWDecoding,WebRtcHWEncoding,WebRtcAecRefinedAdaptiveFilter,WebRtcHybridAgc",
                "--force-fieldtrials=WebRTC-Audio-Red-For-Opus/Disabled/WebRTC-Audio-SendSideBwe/Disabled/",
                "--disable-audio-processing",
                "--disable-webrtc-apm-in-audio-service",
            ],
            permissions=["camera", "microphone"],
        )
        self._browser = context  # persistent context acts as browser

        self._page = await context.new_page()
        print(f"[meet] Navigating to {self.meet_url}")
        await self._page.goto(self.meet_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # let page settle

        # Take screenshot for debugging
        await self._page.screenshot(path="/tmp/meet_debug.png")
        print("[meet] Screenshot saved to /tmp/meet_debug.png")

        # Handle name input (for non-signed-in join)
        await self._try_enter_name()

        # Dismiss mic/camera pre-join toggles and click Join
        await self._dismiss_prejoin()

        # Route Chrome's audio output to the virtual sink so the bot can hear the meeting
        await asyncio.sleep(2)
        from audio_pipeline import move_chrome_audio_to_capture_sink
        move_chrome_audio_to_capture_sink()

        # Log mic state for debugging
        try:
            btn = self._page.locator('[aria-label*="microphone" i]').first
            label = await btn.get_attribute("aria-label")
            print(f"[meet] Joined meeting. Mic button label: '{label}'")
        except Exception:
            print("[meet] Joined meeting.")

    async def _try_enter_name(self):
        # Dismiss "Sign in with Google" popup if present
        try:
            got_it = self._page.get_by_role("button", name="Got it")
            await got_it.click(timeout=3000)
        except Exception:
            pass

        # Fill name if joining as guest
        try:
            name_input = self._page.get_by_placeholder("Your name")
            await name_input.wait_for(timeout=5000)
            await name_input.fill(self.display_name)
        except Exception:
            pass  # Already signed in or field not present

    async def _dismiss_prejoin(self):
        """Click through the pre-join screen — handles all Meet screen states."""
        page = self._page

        # Wait for page to fully load
        await asyncio.sleep(2)

        # Select DecepticonMic from the mic dropdown if available
        try:
            mic_dropdown = page.locator('[aria-label*="microphone" i], [data-prober="microphone-select"]').first
            await mic_dropdown.click(timeout=3000)
            await asyncio.sleep(1)
            decepticon_opt = page.get_by_text("DecepticonMic", exact=False)
            await decepticon_opt.click(timeout=2000)
        except Exception:
            pass  # Use default if not found

        # Turn off camera if button exists
        try:
            cam_btn = page.locator('[aria-label*="camera" i]').first
            await cam_btn.click(timeout=3000)
        except Exception:
            pass

        # Try every possible join button variant Meet uses
        join_selectors = [
            # Role-based (most reliable)
            ("role", "Join now"),
            ("role", "Ask to join"),
            ("role", "Join"),
            ("role", "Continue without microphone"),
            # Data-attribute based
            ("attr", '[data-idom-class*="join" i]'),
            # Text content based
            ("text", "Join now"),
            ("text", "Ask to join"),
            ("text", "Join"),
        ]

        for attempt in range(3):  # retry up to 3 times
            for sel_type, sel_val in join_selectors:
                try:
                    if sel_type == "role":
                        btn = page.get_by_role("button", name=sel_val)
                        await btn.click(timeout=3000)
                    elif sel_type == "attr":
                        btn = page.locator(sel_val).first
                        await btn.click(timeout=3000)
                    elif sel_type == "text":
                        btn = page.get_by_text(sel_val, exact=True)
                        await btn.click(timeout=2000)
                    print(f"[meet] Clicked join button: '{sel_val}'")
                    await asyncio.sleep(3)
                    await page.screenshot(path="/tmp/meet_after_join.png")
                    return
                except Exception:
                    continue

            print(f"[meet] Join button not found (attempt {attempt+1}/3), waiting...")
            await asyncio.sleep(3)
            await page.screenshot(path=f"/tmp/meet_debug_{attempt+1}.png")

        print("[meet] WARNING: Could not click join button. Check /tmp/meet_debug_*.png")

    async def mute(self):
        """Mute mic — click button only if currently unmuted ('Turn off microphone')."""
        try:
            btn = self._page.locator('[aria-label*="microphone" i]').first
            label = await btn.get_attribute("aria-label")
            if label and "turn off" in label.lower():
                await btn.click()
                print("[meet] Mic muted.")
        except Exception:
            pass

    async def unmute(self):
        """Unmute mic — click button only if currently muted ('Turn on microphone')."""
        try:
            btn = self._page.locator('[aria-label*="microphone" i]').first
            label = await btn.get_attribute("aria-label")
            if label and "turn on" in label.lower():
                await btn.click()
                print("[meet] Mic unmuted.")
            else:
                print(f"[meet] Unmute: label was '{label}' — already unmuted or not found.")
        except Exception:
            pass

    async def get_captions_text(self) -> str:
        """Read live captions if enabled."""
        try:
            captions = self._page.locator('[class*="caption" i]')
            texts = await captions.all_inner_texts()
            return " ".join(texts).strip()
        except Exception:
            return ""

    async def leave(self):
        try:
            leave_btn = self._page.get_by_role("button", name="Leave call")
            await leave_btn.click(timeout=3000)
        except Exception:
            pass
        await asyncio.sleep(1)
        try:
            await self._page.close()
            await self._browser.close()  # closes persistent context
        except Exception:
            pass
        await self._playwright.stop()
        print("[meet] Left meeting.")
