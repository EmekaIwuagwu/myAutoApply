import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def find_buttons_in_image(image_path: str) -> List[Dict]:
    """Use OpenCV to detect button-like elements in a screenshot."""
    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path)
        if img is None:
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Threshold to find rectangular regions (likely buttons)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        buttons = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Filter for button-like proportions
            if 50 < w < 400 and 20 < h < 80:
                buttons.append({"x": x, "y": y, "width": w, "height": h, "cx": x + w // 2, "cy": y + h // 2})

        return buttons

    except ImportError:
        logger.warning("OpenCV not available — visual button detection disabled")
        return []
    except Exception as e:
        logger.error(f"Button detection failed: {e}")
        return []


def find_submit_button(image_path: str) -> Optional[Tuple[int, int]]:
    """Find the most likely submit button position in a screenshot."""
    buttons = find_buttons_in_image(image_path)
    if not buttons:
        return None

    # Prefer buttons in the lower portion of the screen
    height_threshold = 0.6
    try:
        import cv2
        img = cv2.imread(image_path)
        if img is not None:
            screen_height = img.shape[0]
            lower_buttons = [b for b in buttons if b["y"] > screen_height * height_threshold]
            if lower_buttons:
                # Pick the rightmost lower button (typical submit location)
                best = max(lower_buttons, key=lambda b: b["x"])
                return (best["cx"], best["cy"])
    except Exception:
        pass

    # Fallback: last button
    if buttons:
        last = buttons[-1]
        return (last["cx"], last["cy"])
    return None
