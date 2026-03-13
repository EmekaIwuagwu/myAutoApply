import os
from dotenv import load_dotenv

load_dotenv()

# Detect if running on Render.com
ON_RENDER = os.getenv("RENDER", "false").lower() == "true"

# On Render, persistent data lives on a mounted disk at /data
# Locally it lives next to the project root
_DATA_ROOT = "/data" if ON_RENDER else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class Config:
    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "autoapply-dev-secret-change-in-prod")
    # Never run debug=True in production
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true" and not ON_RENDER
    PORT = int(os.getenv("PORT", "5000"))

    # ── Database ─────────────────────────────────────────────────────────────
    # Default: file-based SQLite. On Render use /data so it survives redeploys.
    _default_db = f"sqlite:///{_DATA_ROOT}/autoapply.db"
    DATABASE_URL = os.getenv("DATABASE_URL", _default_db)

    # ── Ollama (local LLM — optional on Render) ───────────────────────────────
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # ── Agent behaviour ───────────────────────────────────────────────────────
    MIN_FIT_SCORE = float(os.getenv("MIN_FIT_SCORE", "0.65"))
    MAX_DAILY_APPLICATIONS = int(os.getenv("MAX_DAILY_APPLICATIONS", "20"))
    SEARCH_INTERVAL_MINUTES = int(os.getenv("SEARCH_INTERVAL_MINUTES", "60"))

    # ── Browser ───────────────────────────────────────────────────────────────
    # Always headless on Render (no display); show browser locally by default
    HEADLESS = os.getenv("HEADLESS", "true" if ON_RENDER else "false").lower() == "true"
    SLOW_MO = int(os.getenv("SLOW_MO", "50"))

    # ── File storage ──────────────────────────────────────────────────────────
    RESUME_UPLOAD_FOLDER = os.getenv(
        "RESUME_UPLOAD_FOLDER", os.path.join(_DATA_ROOT, "uploads", "resumes")
    )
    SCREENSHOT_FOLDER = os.getenv(
        "SCREENSHOT_FOLDER", os.path.join(_DATA_ROOT, "uploads", "screenshots")
    )

    # ── Search defaults (overridable via Settings UI) ─────────────────────────
    DEFAULT_KEYWORDS = os.getenv(
        "DEFAULT_KEYWORDS", "Python Developer,AI Engineer,Backend Engineer"
    ).split(",")
    DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Remote")

    # ── Platform credentials (set via Settings UI or env) ────────────────────
    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")
    INDEED_EMAIL = os.getenv("INDEED_EMAIL", "")
    INDEED_PASSWORD = os.getenv("INDEED_PASSWORD", "")


config = Config()
