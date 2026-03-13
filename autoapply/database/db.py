import fcntl
import os
import tempfile

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError

db = SQLAlchemy()


def init_db(app):
    """Initialize the database with the Flask app."""
    db.init_app(app)
    with app.app_context():
        # Use a file lock so that concurrent gunicorn workers don't race on
        # CREATE TABLE.  The second worker will block until the first finishes,
        # then see the tables already exist and skip them cleanly.
        lock_path = os.path.join(tempfile.gettempdir(), "autoapply_db_init.lock")
        with open(lock_path, "w") as _lock:
            fcntl.flock(_lock, fcntl.LOCK_EX)
            try:
                with db.engine.begin() as conn:
                    db.metadata.create_all(conn, checkfirst=True)
            except OperationalError as exc:
                if "already exists" not in str(exc).lower():
                    raise
            finally:
                fcntl.flock(_lock, fcntl.LOCK_UN)
        _seed_default_config(app)


def _seed_default_config(app):
    """Insert default agent config values if not present."""
    from .models import AgentConfig

    with app.app_context():
        defaults = {
            "max_daily_applications": "20",
            "min_fit_score": "0.65",
            "search_keywords": "Python Developer,AI Engineer,Backend Engineer",
            "search_location": "Remote",
            "blacklisted_companies": "",
            "ollama_model": "llama3",
            "ollama_url": "http://localhost:11434",
            "auto_run_enabled": "false",
            "run_interval_minutes": "60",
            "tailor_resume": "true",
            "generate_cover_letter": "true",
        }
        for key, value in defaults.items():
            existing = AgentConfig.query.filter_by(key=key).first()
            if not existing:
                db.session.add(AgentConfig(key=key, value=value))
        db.session.commit()


def get_config_value(key: str, default: str = "") -> str:
    """Get a config value by key from the database."""
    from .models import AgentConfig

    record = AgentConfig.query.filter_by(key=key).first()
    return record.value if record else default


def set_config_value(key: str, value: str):
    """Set a config value in the database."""
    from .models import AgentConfig

    record = AgentConfig.query.filter_by(key=key).first()
    if record:
        record.value = value
    else:
        db.session.add(AgentConfig(key=key, value=value))
    db.session.commit()
