import logging
import os
from datetime import datetime
from pathlib import Path

from ..config import config

logger = logging.getLogger(__name__)


async def take_screenshot(page, prefix: str = "screenshot") -> str:
    """Take a screenshot and save it to the screenshots folder."""
    folder = Path(config.SCREENSHOT_FOLDER)
    folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = str(folder / filename)

    try:
        await page.screenshot(path=filepath, full_page=True)
        logger.info(f"Screenshot saved: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return ""


def get_relative_path(abs_path: str) -> str:
    """Convert absolute path to relative path for storage."""
    if not abs_path:
        return ""
    try:
        return os.path.relpath(abs_path)
    except ValueError:
        return abs_path
