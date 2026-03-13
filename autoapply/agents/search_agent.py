import logging
from datetime import datetime
from typing import List, Dict

from ..database.db import db, get_config_value
from ..database.models import JobListing, AgentLog
from ..config import config

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent responsible for finding and saving job listings."""

    def __init__(self, app=None):
        self.app = app
        self.name = "SearchAgent"

    def _log(self, action: str, status: str, message: str):
        """Write a log entry to the database."""
        if not self.app:
            logger.info(f"[{self.name}] {action}: {message}")
            return
        with self.app.app_context():
            log = AgentLog(
                agent_name=self.name,
                action=action,
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
            )
            db.session.add(log)
            db.session.commit()

    async def run(self, keywords: List[str] = None, location: str = None) -> int:
        """Search all platforms and save new jobs to database. Returns count of new jobs."""
        keywords = keywords or get_config_value("search_keywords", "Python Developer").split(",")
        location = location or get_config_value("search_location", "Remote")
        keywords = [k.strip() for k in keywords if k.strip()]

        self._log("start", "info", f"Starting search for: {', '.join(keywords)} @ {location}")
        total_new = 0

        for keyword in keywords:
            # Indeed
            try:
                count = await self._search_indeed(keyword, location)
                total_new += count
            except Exception as e:
                self._log("indeed_search", "error", f"Indeed search failed for '{keyword}': {e}")

            # Remote.co
            try:
                count = await self._search_remoteco(keyword, location)
                total_new += count
            except Exception as e:
                self._log("remoteco_search", "error", f"Remote.co search failed for '{keyword}': {e}")

            # LinkedIn (only if credentials configured)
            linkedin_email = get_config_value("linkedin_email", "")
            linkedin_password = get_config_value("linkedin_password", "")
            if linkedin_email and linkedin_password:
                try:
                    count = await self._search_linkedin(keyword, location, linkedin_email, linkedin_password)
                    total_new += count
                except Exception as e:
                    self._log("linkedin_search", "error", f"LinkedIn search failed for '{keyword}': {e}")

        self._log("complete", "success", f"Search complete. {total_new} new jobs found.")
        return total_new

    async def _search_indeed(self, keyword: str, location: str) -> int:
        """Search Indeed and save jobs."""
        from ..scrapers.indeed_scraper import IndeedScraper
        scraper = IndeedScraper()
        jobs = await scraper.search_jobs(keyword, location, max_pages=2)
        return self._save_jobs(jobs)

    async def _search_remoteco(self, keyword: str, location: str) -> int:
        """Search Remote.co and save jobs."""
        from ..scrapers.remoteco_scraper import RemoteCoScraper
        scraper = RemoteCoScraper()
        jobs = await scraper.search_jobs(keyword, location)
        return self._save_jobs(jobs)

    async def _search_linkedin(
        self, keyword: str, location: str, email: str, password: str
    ) -> int:
        """Search LinkedIn and save jobs."""
        from ..scrapers.linkedin_scraper import LinkedInScraper
        scraper = LinkedInScraper()
        jobs = await scraper.search_jobs(keyword, location, max_pages=2, email=email, password=password)
        return self._save_jobs(jobs)

    def _save_jobs(self, jobs: List[Dict]) -> int:
        """Save job listings to database, skipping duplicates. Returns count of new jobs."""
        if not self.app:
            logger.warning("No Flask app context — cannot save jobs")
            return 0

        new_count = 0
        with self.app.app_context():
            for job_data in jobs:
                url = job_data.get("url", "").strip()
                if not url:
                    continue

                existing = JobListing.query.filter_by(url=url).first()
                if existing:
                    continue

                try:
                    job = JobListing(
                        platform=job_data.get("platform", "unknown"),
                        title=job_data.get("title", ""),
                        company=job_data.get("company", ""),
                        location=job_data.get("location", ""),
                        url=url,
                        description=job_data.get("description", ""),
                        salary_range=job_data.get("salary_range", ""),
                        posted_date=job_data.get("posted_date", ""),
                        status="new",
                        scraped_at=datetime.utcnow(),
                    )
                    db.session.add(job)
                    new_count += 1
                except Exception as e:
                    logger.debug(f"Error saving job {url}: {e}")
                    db.session.rollback()

            db.session.commit()

        self._log(
            "save_jobs",
            "success" if new_count > 0 else "info",
            f"Saved {new_count} new jobs",
        )
        return new_count
