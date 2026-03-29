"""
One-time login setup script.

Opens a visible browser window so the user can log into LinkedIn (and optionally
Indeed/Glassdoor). After login is detected, cookies and localStorage are saved
to data/browser_state.json for reuse by the scraping agent.

Usage:
    python setup_login.py
"""

import asyncio
import os

from playwright.async_api import async_playwright

STATE_PATH = "data/browser_state.json"


async def setup():
    os.makedirs("data", exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,  # visible window so user can log in
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--hide-scrollbars",
                "--disable-web-resources",
                "--disable-features=VizDisplayCompositor",
                "--disable-site-isolation-trials",
            ],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="UTC",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = await context.new_page()

        print("\n╔══════════════════════════════════════════════════╗")
        print("║          Job Finder — Login Setup                ║")
        print("╠══════════════════════════════════════════════════╣")
        print("║  A browser window has opened.                    ║")
        print("║  Please log in to LinkedIn.                      ║")
        print("║  (You can also log into Indeed/Glassdoor if you  ║")
        print("║   want — just open new tabs.)                    ║")
        print("║                                                  ║")
        print("║  When done, come back here and press ENTER.      ║")
        print("╚══════════════════════════════════════════════════╝\n")

        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        # Wait for user to finish logging in
        input("Press ENTER after you have logged in... ")

        # Save the full browser state (cookies + localStorage)
        await context.storage_state(path=STATE_PATH)
        print(f"\n✓ Browser state saved to {STATE_PATH}")
        print("  Future runs of the agent will use these cookies automatically.\n")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(setup())
