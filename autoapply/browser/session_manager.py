import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages login sessions and cookies for each platform."""

    def __init__(self, app=None):
        self.app = app

    def save_session(self, platform: str, username: str, cookies: list):
        """Save session cookies for a platform to the database."""
        from ..database.models import PlatformSession
        from ..database.db import db

        with self.app.app_context():
            session = PlatformSession.query.filter_by(platform=platform).first()
            if session:
                session.username = username
                session.session_cookies = json.dumps(cookies)
                session.is_active = True
                session.last_login = datetime.utcnow()
            else:
                session = PlatformSession(
                    platform=platform,
                    username=username,
                    session_cookies=json.dumps(cookies),
                    is_active=True,
                    last_login=datetime.utcnow(),
                )
                db.session.add(session)
            db.session.commit()
            logger.info(f"Session saved for {platform}")

    def load_session(self, platform: str) -> Optional[list]:
        """Load saved cookies for a platform."""
        from ..database.models import PlatformSession

        with self.app.app_context():
            session = PlatformSession.query.filter_by(
                platform=platform, is_active=True
            ).first()
            if session and session.session_cookies:
                return json.loads(session.session_cookies)
        return None

    def invalidate_session(self, platform: str):
        """Mark a session as inactive."""
        from ..database.models import PlatformSession
        from ..database.db import db

        with self.app.app_context():
            session = PlatformSession.query.filter_by(platform=platform).first()
            if session:
                session.is_active = False
                db.session.commit()
                logger.info(f"Session invalidated for {platform}")

    async def apply_cookies(self, context, platform: str) -> bool:
        """Apply saved cookies to a browser context."""
        cookies = self.load_session(platform)
        if cookies:
            try:
                await context.add_cookies(cookies)
                logger.info(f"Cookies applied for {platform}")
                return True
            except Exception as e:
                logger.error(f"Failed to apply cookies for {platform}: {e}")
        return False

    async def capture_cookies(self, context, platform: str, username: str):
        """Capture current browser cookies and save them."""
        try:
            cookies = await context.cookies()
            self.save_session(platform, username, cookies)
        except Exception as e:
            logger.error(f"Failed to capture cookies for {platform}: {e}")
