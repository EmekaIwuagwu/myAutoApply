"""Test: Launch browser, navigate to indeed.com, take screenshot."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_browser_launch():
    from autoapply.browser.playwright_engine import PlaywrightEngine
    engine = PlaywrightEngine(headless=True)

    try:
        await engine.launch()
        print("✓ Browser launched")

        page = await engine.navigate("https://www.example.com")
        print(f"✓ Navigated to: {page.url}")

        content = await engine.get_content(page)
        assert "Example Domain" in content or len(content) > 100
        print(f"✓ Page content retrieved: {len(content)} chars")

        screenshot = await engine.screenshot(path="/tmp/test_screenshot.png", page=page)
        assert os.path.exists("/tmp/test_screenshot.png")
        print("✓ Screenshot saved to /tmp/test_screenshot.png")

    finally:
        await engine.close()
        print("✓ Browser closed")


async def test_human_simulator():
    from autoapply.browser.human_simulator import random_delay, scroll_page, move_mouse_randomly
    from autoapply.browser.playwright_engine import PlaywrightEngine

    engine = PlaywrightEngine(headless=True)
    try:
        await engine.launch()
        page = await engine.navigate("https://www.example.com")

        await random_delay(0.1, 0.3)
        print("✓ random_delay works")

        await scroll_page(page, "down", 100)
        print("✓ scroll_page works")

        await move_mouse_randomly(page, count=2)
        print("✓ move_mouse_randomly works")

    finally:
        await engine.close()


async def test_navigate_indeed():
    from autoapply.browser.playwright_engine import PlaywrightEngine
    from bs4 import BeautifulSoup

    engine = PlaywrightEngine(headless=True)
    try:
        await engine.launch()
        page = await engine.navigate("https://www.indeed.com")
        await asyncio.sleep(2)

        content = await engine.get_content(page)
        soup = BeautifulSoup(content, "lxml")
        title = soup.title.string if soup.title else "no title"
        print(f"✓ Indeed page loaded. Title: {title}")
        assert "indeed" in title.lower() or len(content) > 1000

    finally:
        await engine.close()


if __name__ == "__main__":
    print("Running browser tests...")
    asyncio.run(test_browser_launch())
    asyncio.run(test_human_simulator())
    asyncio.run(test_navigate_indeed())
    print("\n✅ Browser tests complete!")
