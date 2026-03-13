import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..browser.playwright_engine import PlaywrightEngine
from ..browser.human_simulator import random_delay, scroll_page

logger = logging.getLogger(__name__)

REMOTECO_BASE = "https://remote.co"
WWR_BASE = "https://weworkremotely.com"


class RemoteCoScraper:
    """Scraper for remote.co and We Work Remotely."""

    def __init__(self, engine: PlaywrightEngine = None):
        self.engine = engine
        self._owns_engine = engine is None

    async def _get_engine(self) -> PlaywrightEngine:
        if not self.engine:
            self.engine = PlaywrightEngine()
            await self.engine.launch()
        return self.engine

    async def search_jobs(
        self, query: str, location: str = "Remote", max_pages: int = 2
    ) -> List[Dict]:
        """Search remote.co and WWR for jobs."""
        engine = await self._get_engine()
        jobs = []

        # Scrape remote.co
        try:
            remoteco_jobs = await self._scrape_remoteco(engine, query, max_pages)
            jobs.extend(remoteco_jobs)
        except Exception as e:
            logger.error(f"remote.co scraping failed: {e}")

        # Scrape We Work Remotely
        try:
            wwr_jobs = await self._scrape_wwr(engine, query)
            jobs.extend(wwr_jobs)
        except Exception as e:
            logger.error(f"We Work Remotely scraping failed: {e}")

        if self._owns_engine and self.engine:
            await self.engine.close()
            self.engine = None

        logger.info(f"Remote.co/WWR: found {len(jobs)} jobs for '{query}'")
        return jobs

    async def _scrape_remoteco(
        self, engine: PlaywrightEngine, query: str, max_pages: int
    ) -> List[Dict]:
        """Scrape remote.co job listings."""
        jobs = []
        search_url = f"{REMOTECO_BASE}/remote-jobs/search/?search_keywords={query.replace(' ', '+')}"

        page = await engine.navigate(search_url)
        await random_delay(1.5, 3.0)

        content = await engine.get_content(page)
        soup = BeautifulSoup(content, "lxml")

        job_cards = soup.find_all("li", {"class": lambda c: c and "job_listing" in str(c)})
        if not job_cards:
            job_cards = soup.find_all("div", {"class": "card"})

        for card in job_cards[:15]:
            try:
                job = self._parse_remoteco_card(card)
                if job and job.get("url"):
                    # Get full description
                    desc = await self._get_remoteco_description(engine, job["url"])
                    job["description"] = desc
                    jobs.append(job)
                    await random_delay(1.0, 2.0)
            except Exception as e:
                logger.debug(f"Failed to parse remote.co card: {e}")

        return jobs

    def _parse_remoteco_card(self, card) -> Dict:
        """Parse a single remote.co job card."""
        job = {
            "platform": "remoteco",
            "title": "",
            "company": "",
            "location": "Remote",
            "url": "",
            "salary_range": "",
            "posted_date": "",
            "description": "",
            "scraped_at": datetime.utcnow().isoformat(),
        }

        title_el = card.find("h2", {"class": "position"})
        if not title_el:
            title_el = card.find(["h2", "h3"])
        if title_el:
            job["title"] = title_el.get_text(strip=True)

        company_el = card.find("h3", {"class": "company"})
        if not company_el:
            company_el = card.find("span", {"class": "company_name"})
        if company_el:
            job["company"] = company_el.get_text(strip=True)

        link = card.find("a", href=True)
        if link:
            href = link["href"]
            if href.startswith("/"):
                job["url"] = urljoin(REMOTECO_BASE, href)
            elif href.startswith("http"):
                job["url"] = href

        return job

    async def _get_remoteco_description(
        self, engine: PlaywrightEngine, url: str
    ) -> str:
        """Get full job description from remote.co listing."""
        try:
            page = await engine.navigate(url)
            await random_delay(1.0, 2.0)

            content = await engine.get_content(page)
            soup = BeautifulSoup(content, "lxml")

            desc_el = soup.find("div", {"class": "job_description"})
            if not desc_el:
                desc_el = soup.find("section", {"class": "job_description"})
            if desc_el:
                return desc_el.get_text(separator="\n", strip=True)
        except Exception as e:
            logger.debug(f"Could not get remote.co description: {e}")
        return ""

    async def _scrape_wwr(self, engine: PlaywrightEngine, query: str) -> List[Dict]:
        """Scrape We Work Remotely job listings."""
        jobs = []
        # WWR uses category-based browsing; search via their search
        search_url = f"{WWR_BASE}/remote-jobs/search?term={query.replace(' ', '+')}"

        page = await engine.navigate(search_url)
        await random_delay(1.5, 3.0)

        content = await engine.get_content(page)
        soup = BeautifulSoup(content, "lxml")

        # WWR job structure
        sections = soup.find_all("section", {"class": "jobs"})
        for section in sections:
            cards = section.find_all("li")
            for card in cards[:10]:
                try:
                    job = self._parse_wwr_card(card)
                    if job and job.get("url") and job.get("title"):
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Failed to parse WWR card: {e}")

        return jobs

    def _parse_wwr_card(self, card) -> Dict:
        """Parse a single We Work Remotely job card."""
        job = {
            "platform": "remoteco",
            "title": "",
            "company": "",
            "location": "Remote",
            "url": "",
            "salary_range": "",
            "posted_date": "",
            "description": "",
            "scraped_at": datetime.utcnow().isoformat(),
        }

        link = card.find("a", href=True)
        if not link:
            return job

        href = link["href"]
        if href.startswith("/"):
            job["url"] = urljoin(WWR_BASE, href)
        else:
            job["url"] = href

        spans = card.find_all("span")
        if len(spans) >= 2:
            job["company"] = spans[0].get_text(strip=True)
            job["title"] = spans[1].get_text(strip=True)
        elif link:
            job["title"] = link.get_text(strip=True)

        return job
