from playwright.async_api import Browser, BrowserContext, async_playwright
import os

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)",
]


class BrowserManager:
    def __init__(self, headless: bool = True, storage_state: str | None = None):
        self.headless = headless
        self.storage_state = storage_state
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self):
        self._playwright = await async_playwright().start()

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox", 
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--hide-scrollbars",
            ],
        )

        import random
        from tools.browser.browser_manager import USER_AGENTS

        context_kwargs = {
            "user_agent": random.choice(USER_AGENTS),
            "viewport": {"width": 1280, "height": 800},
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
            "locale": "en-US",
            "timezone_id": "UTC",
        }
    
        context_kwargs["extra_http_headers"] = {
            "Accept-Language": "en-US,en;q=0.9",
        }

        if self.storage_state:
            if isinstance(self.storage_state, str) and os.path.exists(self.storage_state):
                context_kwargs["storage_state"] = self.storage_state
            elif isinstance(self.storage_state, dict):
                context_kwargs["storage_state"] = self.storage_state

        self._context = await self._browser.new_context(**context_kwargs)

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self):
        """
        Opens the browser with a randomly choosen user agent and returns a new page opened in it
        """
        if self._context is None:
            raise RuntimeError("Start BrowserManager first.")
        return await self._context.new_page()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.stop()
