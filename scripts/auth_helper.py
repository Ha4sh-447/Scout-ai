import asyncio
import os
import sys
from playwright.async_api import async_playwright

async def run():
    print("--- Job Finder Authentication Helper ---")
    print("This script will open a browser for you to log in to job platforms.")
    print("Once logged in, the session will be saved to data/browser_state.json.\n")

    os.makedirs("data", exist_ok=True)
    state_path = "data/browser_state.json"

    async with async_playwright() as p:
        # Launch non-headless so user can interact
        browser = await p.chromium.launch(headless=False)
        
        # Create a new context
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()

        # 1. LinkedIn
        print("Opening LinkedIn... Please log in.")
        await page.goto("https://www.linkedin.com/login")
        
        # 2. Wellfound
        print("Opening Wellfound... Please log in.")
        # Open in a new tab or same page
        wellfound_page = await context.new_page()
        await wellfound_page.goto("https://wellfound.com/login")

        print("\n--- ACTION REQUIRED ---")
        print("1. Log in to LinkedIn in the first tab.")
        print("2. Log in to Wellfound in the second tab.")
        print("3. Ensure you are on the 'Jobs' or 'Home' page for both.")
        print("4. Come back here and press ENTER to save the session.")
        
        input("\nPress ENTER when you have finished logging in...")

        # Save the storage state
        await context.storage_state(path=state_path)
        print(f"\n✓ Session state saved to {state_path}")
        
        await browser.close()
        print("Browser closed. You can now run the pipeline.")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")
