# ── Stage 1: Python dependencies ────────────────────────────────────────────
FROM python:3.11-slim AS base

# System packages needed by Playwright/Chromium, Tesseract, OpenCV, pdfplumber
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium runtime deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libdbus-1-3 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    # Fonts (so headless Chromium can render text)
    fonts-liberation fonts-noto-color-emoji \
    # Tesseract OCR
    tesseract-ocr tesseract-ocr-eng \
    # General tools
    wget curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only — saves ~600 MB vs all browsers)
RUN playwright install chromium \
    && playwright install-deps chromium

# ── Stage 2: Application code ────────────────────────────────────────────────
COPY . .

# Create persistent data directories (Render mounts /data as a disk)
RUN mkdir -p /data/uploads/resumes /data/uploads/screenshots

# ── Runtime config ───────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RENDER=true \
    HEADLESS=true \
    PORT=10000

EXPOSE 10000

# gunicorn: 2 workers, gevent async, 120 s timeout (Playwright can be slow)
CMD ["gunicorn", \
     "--bind", "0.0.0.0:10000", \
     "--workers", "2", \
     "--worker-class", "gevent", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "run:app"]
