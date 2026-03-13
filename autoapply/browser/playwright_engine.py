import asyncio
import logging
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from fake_useragent import UserAgent

from ..config import config

logger = logging.getLogger(__name__)


class PlaywrightEngine:
    """Async Playwright browser controller with anti-bot measures."""

    def __init__(self, headless: bool = None, slow_mo: int = None):
        self.headless = headless if headless is not None else config.HEADLESS
        self.slow_mo = slow_mo if slow_mo is not None else config.SLOW_MO
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._ua = UserAgent()

    async def launch(self, user_data_dir: str = None):
        """Launch the browser."""
        self._playwright = await async_playwright().start()

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1920,1080",
        ]

        if user_data_dir:
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=launch_args,
                user_agent=self._ua.random,
                viewport={"width": 1920, "height": 1080},
            )
            self._browser = None
        else:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=launch_args,
            )
            self._context = await self._browser.new_context(
                user_agent=self._ua.random,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )

        # Inject stealth scripts
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
        """)

        logger.info("Browser launched")

    async def new_page(self) -> Page:
        """Create a new browser page."""
        if not self._context:
            raise RuntimeError("Browser not launched. Call launch() first.")
        self._page = await self._context.new_page()
        return self._page

    async def navigate(self, url: str, page: Page = None) -> Page:
        """Navigate to a URL."""
        page = page or self._page
        if not page:
            page = await self.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await self.wait_random(500, 1500)
        return page

    async def safe_click(self, selector: str, page: Page = None):
        """Wait for element, scroll to it, then click."""
        page = page or self._page
        await page.wait_for_selector(selector, timeout=10000)
        element = await page.query_selector(selector)
        if element:
            await element.scroll_into_view_if_needed()
            await self.wait_random(200, 600)
            await element.click()
        else:
            raise ValueError(f"Element not found: {selector}")

    async def safe_fill(self, selector: str, text: str, page: Page = None):
        """Fill a field with human-like typing delays."""
        page = page or self._page
        await page.wait_for_selector(selector, timeout=10000)
        element = await page.query_selector(selector)
        if element:
            await element.scroll_into_view_if_needed()
            await element.click()
            await self.wait_random(100, 300)
            # Clear field first
            await element.fill("")
            await self.wait_random(100, 200)
            # Type character by character
            for char in text:
                await element.type(char, delay=random.randint(50, 150))
        else:
            raise ValueError(f"Element not found: {selector}")

    async def wait_random(self, min_ms: int = 500, max_ms: int = 2000):
        """Random delay between actions."""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def screenshot(self, path: str = None, page: Page = None) -> bytes:
        """Take a screenshot."""
        page = page or self._page
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=path, full_page=True)
            logger.info(f"Screenshot saved: {path}")
        return await page.screenshot(full_page=True)

    async def get_content(self, page: Page = None) -> str:
        """Get page HTML content."""
        page = page or self._page
        return await page.content()

    async def close(self):
        """Close browser and clean up."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def context(self) -> Optional[BrowserContext]:
        return self._context
