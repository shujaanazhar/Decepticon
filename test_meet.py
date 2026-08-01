"""
Smoke test for the local backend's browser setup.

Launches your configured Chrome profile and opens meet.google.com. If this
can't reach the lobby, nothing further will work — check CHROME_PROFILE_DIR
and CHROME_BINARY in .env before debugging anything else.

    .venv/bin/python test_meet.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot"))

import config


async def test():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[test] Playwright isn't installed — that's local-backend only.")
        return 1

    print(f"[test] Profile: {config.CHROME_PROFILE_DIR} ({config.CHROME_PROFILE_NAME})")
    print(f"[test] Chrome:  {config.CHROME_BINARY}")
    sys.stdout.flush()

    playwright = await async_playwright().start()
    try:
        context = await playwright.chromium.launch_persistent_context(
            config.CHROME_PROFILE_DIR,
            executable_path=config.CHROME_BINARY,
            headless=config.HEADLESS,
            args=[
                f"--profile-directory={config.CHROME_PROFILE_NAME}",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        print("[test] Browser up, opening meet.google.com...")
        sys.stdout.flush()

        page = await context.new_page()
        await page.goto("https://meet.google.com", wait_until="domcontentloaded", timeout=15000)
        print(f"[test] Landed on: {page.url}")

        await page.screenshot(path="/tmp/meet_test.png")
        print("[test] Screenshot: /tmp/meet_test.png")

        if "signin" in page.url or "accounts.google" in page.url:
            print("[test] WARNING: redirected to sign-in — this profile isn't logged in.")
            print("[test] Open that profile manually, sign in to Google, then retry.")

        await context.close()
        return 0
    except Exception as exc:
        print(f"[test] ERROR: {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await playwright.stop()


if __name__ == "__main__":
    sys.exit(asyncio.run(test()))
