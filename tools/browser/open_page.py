import asyncio
import random

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser_manager import BrowserManager

PLATFORM_DELAYS = {
    "linkedin": (3.0, 6.0),
    "indeed": (2.0, 4.0),
    "reddit": (1.0, 2.0),
    "generic": (1.0, 2.0),
}


async def open_page(
    bm: BrowserManager,
    url: str,
    platform: str = "generic",
    retries: int = 3,
    wait_until: str = "domcontentloaded",
) -> Page:
    """Navigate to a page."""
    delay_range = PLATFORM_DELAYS.get(platform, (1.0, 2.0))

    for attempt in range(1, retries + 1):
        try:
            page = await bm.new_page()

            await asyncio.sleep(random.uniform(*delay_range))

            await page.goto(url, wait_until=wait_until, timeout=30_000)

            if platform in ("linkedin", "indeed"):
                await page.wait_for_load_state("networkidle", timeout=15_000)

            return page
        except PlaywrightTimeoutError as e:
            if attempt == retries:
                raise RuntimeError(
                    f"Failed to load {url} after {retries} attempts: {e}"
                )
            await asyncio.sleep(2**attempt)
