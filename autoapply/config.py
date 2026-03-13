import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///autoapply.db")

    # Ollama
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

    # Agent Behavior
    MIN_FIT_SCORE = float(os.getenv("MIN_FIT_SCORE", "0.65"))
    MAX_DAILY_APPLICATIONS = int(os.getenv("MAX_DAILY_APPLICATIONS", "20"))
    SEARCH_INTERVAL_MINUTES = int(os.getenv("SEARCH_INTERVAL_MINUTES", "60"))

    # Browser
    HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
    SLOW_MO = int(os.getenv("SLOW_MO", "50"))

    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    RESUME_UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads", "resumes")
    SCREENSHOT_FOLDER = os.path.join(BASE_DIR, "..", "uploads", "screenshots")

    # Search Keywords (defaults, overridable via UI)
    DEFAULT_KEYWORDS = os.getenv(
        "DEFAULT_KEYWORDS", "Python Developer,AI Engineer,Backend Engineer"
    ).split(",")
    DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "Remote")

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "autoapply-dev-secret-change-in-prod")
    DEBUG = os.getenv("FLASK_DEBUG", "true").lower() == "true"

    # LinkedIn credentials (stored in DB/env, never hardcoded)
    LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
    LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

    # Indeed credentials
    INDEED_EMAIL = os.getenv("INDEED_EMAIL", "")
    INDEED_PASSWORD = os.getenv("INDEED_PASSWORD", "")


config = Config()
