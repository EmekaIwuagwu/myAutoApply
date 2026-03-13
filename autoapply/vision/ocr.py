import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_image(image_path: str) -> str:
    """Extract text from an image using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract not available — OCR disabled")
        return ""
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return ""


def extract_text_from_bytes(image_bytes: bytes) -> str:
    """Extract text from image bytes using Tesseract OCR."""
    try:
        import pytesseract
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract not available — OCR disabled")
        return ""
    except Exception as e:
        logger.error(f"OCR from bytes failed: {e}")
        return ""
