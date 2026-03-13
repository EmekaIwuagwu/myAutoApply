import asyncio
import random
import logging

logger = logging.getLogger(__name__)


async def random_delay(min_s: float = 0.5, max_s: float = 3.0):
    """Async sleep with randomness to simulate human timing."""
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


async def human_type(page, selector: str, text: str):
    """Type text character by character with variable speed."""
    await page.wait_for_selector(selector, timeout=10000)
    element = await page.query_selector(selector)
    if not element:
        raise ValueError(f"Element not found: {selector}")

    await element.scroll_into_view_if_needed()
    await element.click()
    await asyncio.sleep(random.uniform(0.1, 0.3))

    for i, char in enumerate(text):
        # Vary typing speed — sometimes fast, sometimes slow
        if random.random() < 0.05:  # 5% chance of a longer pause (thinking)
            await asyncio.sleep(random.uniform(0.3, 0.8))
        delay_ms = random.randint(40, 180)
        await element.type(char, delay=delay_ms)

    # Short pause after typing
    await asyncio.sleep(random.uniform(0.1, 0.4))


async def scroll_page(page, direction: str = "down", amount: int = 300):
    """Simulate natural page scrolling."""
    scroll_amount = amount if direction == "down" else -amount
    # Scroll in small increments to look natural
    steps = random.randint(3, 6)
    per_step = scroll_amount // steps

    for _ in range(steps):
        await page.mouse.wheel(0, per_step + random.randint(-20, 20))
        await asyncio.sleep(random.uniform(0.05, 0.15))


async def move_mouse_randomly(page, count: int = 3):
    """Perform random mouse movements before actions."""
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    width = viewport.get("width", 1280)
    height = viewport.get("height", 720)

    for _ in range(count):
        x = random.randint(100, width - 100)
        y = random.randint(100, height - 100)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.05, 0.2))


async def human_click(page, selector: str):
    """Human-like click: move mouse near element, pause, then click."""
    await page.wait_for_selector(selector, timeout=10000)
    element = await page.query_selector(selector)
    if not element:
        raise ValueError(f"Element not found: {selector}")

    # Scroll into view
    await element.scroll_into_view_if_needed()
    await asyncio.sleep(random.uniform(0.1, 0.3))

    # Move mouse near the element first
    box = await element.bounding_box()
    if box:
        # Add slight randomness to click position within the element
        x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
        await page.mouse.move(x + random.randint(-5, 5), y + random.randint(-5, 5))
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await page.mouse.click(x, y)
    else:
        await element.click()


async def simulate_reading(page, min_s: float = 1.0, max_s: float = 4.0):
    """Simulate reading a page by scrolling slowly and pausing."""
    await scroll_page(page, "down", random.randint(200, 500))
    await asyncio.sleep(random.uniform(min_s, max_s))
    await scroll_page(page, "down", random.randint(100, 300))
    await asyncio.sleep(random.uniform(0.5, 2.0))
