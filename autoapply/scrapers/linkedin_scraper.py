import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ..browser.playwright_engine import PlaywrightEngine
from ..browser.human_simulator import random_delay, human_type, scroll_page, simulate_reading
from ..browser.session_manager import SessionManager

logger = logging.getLogger(__name__)

LINKEDIN_BASE = "https://www.linkedin.com"


class LinkedInScraper:
    """Scraper for LinkedIn job listings with login support."""

    def __init__(self, engine: PlaywrightEngine = None, session_mgr: SessionManager = None):
        self.engine = engine
        self.session_mgr = session_mgr
        self._owns_engine = engine is None
        self._logged_in = False

    async def _get_engine(self) -> PlaywrightEngine:
        if not self.engine:
            self.engine = PlaywrightEngine()
            await self.engine.launch()
        return self.engine

    async def login(self, email: str, password: str) -> bool:
        """Log into LinkedIn."""
        engine = await self._get_engine()

        # Try loading saved session first
        if self.session_mgr:
            applied = await self.session_mgr.apply_cookies(engine.context, "linkedin")
            if applied:
                # Verify session is valid
                page = await engine.navigate(f"{LINKEDIN_BASE}/feed/")
                await random_delay(2.0, 3.0)
                content = await engine.get_content(page)
                if "feed" in page.url or "mynetwork" in page.url:
                    self._logged_in = True
                    logger.info("LinkedIn: resumed saved session")
                    return True

        # Fresh login
        try:
            page = await engine.navigate(f"{LINKEDIN_BASE}/login")
            await random_delay(1.5, 2.5)

            await human_type(page, "#username", email)
            await random_delay(0.5, 1.0)
            await human_type(page, "#password", password)
            await random_delay(0.5, 1.2)

            await engine.safe_click("button[type='submit']")
            await random_delay(3.0, 5.0)

            # Check if login successful
            if "feed" in page.url or "checkpoint" not in page.url:
                self._logged_in = True
                if self.session_mgr:
                    await self.session_mgr.capture_cookies(engine.context, "linkedin", email)
                logger.info("LinkedIn: login successful")
                return True
            else:
                logger.error("LinkedIn: login may have failed or hit checkpoint")
                return False

        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False

    async def search_jobs(
        self,
        query: str,
        location: str = "Remote",
        max_pages: int = 3,
        email: str = "",
        password: str = "",
    ) -> List[Dict]:
        """Search LinkedIn for jobs."""
        engine = await self._get_engine()

        if not self._logged_in and email and password:
            await self.login(email, password)

        jobs = []
        for page_num in range(max_pages):
            start = page_num * 25
            params = {
                "keywords": query,
                "location": location,
                "start": start,
                "f_WT": "2",  # Remote filter
                "sortBy": "DD",  # Date
            }
            url = f"{LINKEDIN_BASE}/jobs/search/?{urlencode(params)}"

            try:
                page = await engine.navigate(url)
                await random_delay(2.0, 4.0)
                await scroll_page(page, "down", 500)
                await random_delay(1.0, 2.0)

                content = await engine.get_content(page)
                soup = BeautifulSoup(content, "lxml")

                # Job cards
                cards = soup.find_all(
                    "div",
                    {"class": lambda c: c and "job-search-card" in str(c)},
                )
                if not cards:
                    cards = soup.find_all("li", {"class": lambda c: c and "jobs-search__results-list" in str(c)})

                if not cards:
                    logger.warning(f"LinkedIn: no cards found on page {page_num + 1}")
                    break

                for card in cards:
                    try:
                        job = self._parse_job_card(card)
                        if job and job.get("url"):
                            jobs.append(job)
                    except Exception as e:
                        logger.debug(f"LinkedIn card parse error: {e}")

                await random_delay(2.0, 4.0)

            except Exception as e:
                logger.error(f"LinkedIn search error on page {page_num + 1}: {e}")
                break

        # Get descriptions
        for job in jobs[:15]:
            try:
                desc, easy_apply = await self._get_job_detail(engine, job["url"])
                job["description"] = desc
                job["easy_apply"] = easy_apply
                await random_delay(1.5, 3.0)
            except Exception as e:
                logger.debug(f"LinkedIn description error: {e}")
                job["description"] = ""
                job["easy_apply"] = False

        if self._owns_engine and self.engine:
            await self.engine.close()
            self.engine = None

        logger.info(f"LinkedIn: found {len(jobs)} jobs for '{query}'")
        return jobs

    def _parse_job_card(self, card) -> Dict:
        """Parse a LinkedIn job card."""
        job = {
            "platform": "linkedin",
            "title": "",
            "company": "",
            "location": "",
            "url": "",
            "salary_range": "",
            "posted_date": "",
            "description": "",
            "easy_apply": False,
            "scraped_at": datetime.utcnow().isoformat(),
        }

        title_el = card.find(["h3", "h2"], {"class": lambda c: c and "title" in str(c).lower()})
        if title_el:
            job["title"] = title_el.get_text(strip=True)

        company_el = card.find(["h4", "a"], {"class": lambda c: c and "company" in str(c).lower()})
        if company_el:
            job["company"] = company_el.get_text(strip=True)

        loc_el = card.find("span", {"class": lambda c: c and "location" in str(c).lower()})
        if loc_el:
            job["location"] = loc_el.get_text(strip=True)

        link = card.find("a", {"class": lambda c: c and "job-search-card__title-link" in str(c)})
        if not link:
            link = card.find("a", href=lambda h: h and "/jobs/view/" in str(h))
        if link and link.get("href"):
            href = link["href"].split("?")[0]
            job["url"] = urljoin(LINKEDIN_BASE, href) if href.startswith("/") else href

        salary_el = card.find("span", {"class": lambda c: c and "salary" in str(c).lower()})
        if salary_el:
            job["salary_range"] = salary_el.get_text(strip=True)

        time_el = card.find("time")
        if time_el:
            job["posted_date"] = time_el.get("datetime", time_el.get_text(strip=True))

        return job

    async def _get_job_detail(
        self, engine: PlaywrightEngine, url: str
    ) -> tuple[str, bool]:
        """Get job description and detect Easy Apply."""
        try:
            page = await engine.navigate(url)
            await random_delay(1.5, 3.0)
            await simulate_reading(page)

            content = await engine.get_content(page)
            soup = BeautifulSoup(content, "lxml")

            # Description
            desc_el = soup.find("div", {"class": lambda c: c and "description__text" in str(c)})
            description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

            # Easy Apply detection
            easy_apply = bool(
                soup.find("button", string=lambda s: s and "Easy Apply" in s)
                or soup.find("span", string=lambda s: s and "Easy Apply" in s)
            )

            return description, easy_apply

        except Exception as e:
            logger.debug(f"LinkedIn job detail error: {e}")
            return "", False
