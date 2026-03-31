import asyncio, os, sys
from dotenv import load_dotenv
load_dotenv()

async def test():
    try:
        from playwright.async_api import async_playwright
        print('[test] Starting playwright...'); sys.stdout.flush()
        p = await async_playwright().start()
        print('[test] Launching browser...'); sys.stdout.flush()
        context = await p.chromium.launch_persistent_context(
            '/home/user/.config/google-chrome-bot',
            executable_path='/usr/bin/google-chrome',
            headless=False,
            args=['--profile-directory=Default','--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage'],
        )
        print('[test] Browser launched, opening page...'); sys.stdout.flush()
        page = await context.new_page()
        print('[test] Navigating to meet.google.com...'); sys.stdout.flush()
        await page.goto('https://meet.google.com', wait_until='domcontentloaded', timeout=15000)
        print('[test] URL after goto:', page.url); sys.stdout.flush()
        await page.screenshot(path='/tmp/meet_test.png')
        print('[test] Done. Screenshot at /tmp/meet_test.png')
        await context.close()
        await p.stop()
    except Exception as e:
        print(f'[test] ERROR: {type(e).__name__}: {e}')
        import traceback; traceback.print_exc()

asyncio.run(test())
