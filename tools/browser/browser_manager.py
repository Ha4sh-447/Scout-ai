from playwright.async_api import Browser, BrowserContext, async_playwright
import os

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BrowserManager:
    def __init__(self, headless: bool = True, storage_state: str | None = None):
        self.headless = headless
        self.storage_state = storage_state
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # Pinned UA — must match what was used when cookies were exported.
    # Rotating UAs is what makes LinkedIn think it's a new device every run.
    _PINNED_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # Persistent profile dir — gives Chromium a stable device identity across runs.
    _PROFILE_DIR = os.path.join(os.path.dirname(__file__), ".chromium_profile")

    async def start(self):
        self._playwright = await async_playwright().start()

        os.makedirs(self._PROFILE_DIR, exist_ok=True)

        launch_args = [
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--hide-scrollbars",
        ]

        context_kwargs = {
            "user_agent": self._PINNED_UA,
            "viewport": {"width": 1280, "height": 800},
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
            "locale": "en-US",
            "timezone_id": "Asia/Kolkata",   # match your actual timezone
            "extra_http_headers": {
                "Accept-Language": "en-US,en;q=0.9",
            },
        }

        if self.storage_state:
            # Persistent context doesn't accept storage_state — inject cookies
            # after launch instead (handled below).
            pass

        # launch_persistent_context gives Chromium a real, stable profile on disk.
        # LinkedIn uses the profile directory's Local State / Preferences files
        # (not just cookies) to recognise a returning device.
        self._context = await self._playwright.chromium.launch_persistent_context(
            self._PROFILE_DIR,
            headless=self.headless,
            args=launch_args,
            **context_kwargs,
        )

        # Inject cookies from storage_state into the persistent context
        if self.storage_state:
            state = self.storage_state
            if isinstance(state, str) and os.path.exists(state):
                import json
                with open(state) as f:
                    state = json.load(f)
            if isinstance(state, dict):
                cookies = state.get("cookies", [])
                if cookies:
                    await self._context.add_cookies(cookies)

        # _browser is unused with persistent context but keep attribute for stop()
        self._browser = None

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._browser:          # None when using persistent context
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_page(self):
        """
        Opens the browser with a randomly choosen user agent and returns a new page opened in it
        """
        if self._context is None:
            raise RuntimeError("Start BrowserManager first.")
        page = await self._context.new_page()
        try:
            import importlib
            stealth_mod = importlib.import_module("playwright_stealth")
            stealth_cls = getattr(stealth_mod, "Stealth")
            await stealth_cls().apply_stealth_async(page)
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except (ImportError, AttributeError) as e:
            import logging
            logging.getLogger(__name__).warning(f"playwright-stealth unavailable ({e}), basic headless bypass will be used.")
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to apply stealth: {e}")
        return page

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.stop()
