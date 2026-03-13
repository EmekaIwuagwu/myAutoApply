import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlencode, urljoin

from bs4 import BeautifulSoup

from ..browser.playwright_engine import PlaywrightEngine
from ..browser.human_simulator import random_delay, scroll_page, simulate_reading

logger = logging.getLogger(__name__)

INDEED_BASE = "https://www.indeed.com"


class IndeedScraper:
    """Scraper for Indeed job listings."""

    def __init__(self, engine: PlaywrightEngine = None):
        self.engine = engine
        self._owns_engine = engine is None

    async def _get_engine(self) -> PlaywrightEngine:
        if not self.engine:
            self.engine = PlaywrightEngine()
            await self.engine.launch()
        return self.engine

    def _build_search_url(self, query: str, location: str = "Remote", start: int = 0) -> str:
        params = {
            "q": query,
            "l": location,
            "start": start,
            "sort": "date",
        }
        if location.lower() == "remote":
            params["remotejob"] = "032b3046-06a3-4876-8dfd-474eb5e7ed11"
        return f"{INDEED_BASE}/jobs?{urlencode(params)}"

    async def search_jobs(
        self, query: str, location: str = "Remote", max_pages: int = 3
    ) -> List[Dict]:
        """Search for jobs and return list of job dicts."""
        engine = await self._get_engine()
        jobs = []

        for page_num in range(max_pages):
            start = page_num * 10
            url = self._build_search_url(query, location, start)
            logger.info(f"Scraping Indeed page {page_num + 1}: {url}")

            try:
                page = await engine.navigate(url)
                await random_delay(1.5, 3.0)
                await scroll_page(page, "down", 400)

                content = await engine.get_content(page)
                soup = BeautifulSoup(content, "lxml")

                job_cards = soup.find_all("div", {"class": lambda c: c and "job_seen_beacon" in c})
                if not job_cards:
                    # Fallback selector
                    job_cards = soup.find_all("td", {"class": "resultContent"})

                if not job_cards:
                    logger.warning(f"No job cards found on page {page_num + 1}")
                    break

                for card in job_cards:
                    try:
                        job = self._parse_job_card(card)
                        if job and job.get("url"):
                            jobs.append(job)
                    except Exception as e:
                        logger.debug(f"Failed to parse job card: {e}")

                await random_delay(2.0, 4.0)

            except Exception as e:
                logger.error(f"Error scraping Indeed page {page_num + 1}: {e}")
                break

        # Get descriptions for each job
        jobs_with_desc = []
        for job in jobs[:20]:  # Limit to 20 per search run
            try:
                desc = await self._get_job_description(engine, job["url"])
                job["description"] = desc
                jobs_with_desc.append(job)
                await random_delay(1.0, 2.5)
            except Exception as e:
                logger.debug(f"Failed to get description for {job.get('url')}: {e}")
                job["description"] = ""
                jobs_with_desc.append(job)

        if self._owns_engine and self.engine:
            await self.engine.close()
            self.engine = None

        logger.info(f"Indeed: found {len(jobs_with_desc)} jobs for '{query}'")
        return jobs_with_desc

    def _parse_job_card(self, card) -> Dict:
        """Parse a single job card from search results."""
        job = {
            "platform": "indeed",
            "title": "",
            "company": "",
            "location": "",
            "url": "",
            "salary_range": "",
            "posted_date": "",
            "description": "",
            "scraped_at": datetime.utcnow().isoformat(),
        }

        # Title
        title_el = card.find("h2", {"class": lambda c: c and "jobTitle" in c})
        if title_el:
            span = title_el.find("span")
            job["title"] = span.get_text(strip=True) if span else title_el.get_text(strip=True)

        # Company
        company_el = card.find("span", {"data-testid": "company-name"})
        if not company_el:
            company_el = card.find("a", {"data-tn-element": "companyName"})
        if company_el:
            job["company"] = company_el.get_text(strip=True)

        # Location
        loc_el = card.find("div", {"data-testid": "text-location"})
        if not loc_el:
            loc_el = card.find("span", {"class": lambda c: c and "companyLocation" in c})
        if loc_el:
            job["location"] = loc_el.get_text(strip=True)

        # URL
        link = card.find("a", {"class": lambda c: c and "jcs-JobTitle" in c})
        if not link:
            link = card.find("a", {"data-jk": True})
        if link and link.get("href"):
            href = link["href"]
            if href.startswith("/"):
                job["url"] = urljoin(INDEED_BASE, href)
            else:
                job["url"] = href

        # Salary
        salary_el = card.find("div", {"class": lambda c: c and "salary-snippet" in c})
        if not salary_el:
            salary_el = card.find("span", {"class": lambda c: c and "estimated-salary" in c})
        if salary_el:
            job["salary_range"] = salary_el.get_text(strip=True)

        # Posted date
        date_el = card.find("span", {"class": lambda c: c and "date" in str(c).lower()})
        if date_el:
            job["posted_date"] = date_el.get_text(strip=True)

        return job

    async def _get_job_description(self, engine: PlaywrightEngine, url: str) -> str:
        """Navigate to job detail page and get full description."""
        try:
            page = await engine.navigate(url)
            await random_delay(1.0, 2.0)
            await simulate_reading(page)

            content = await engine.get_content(page)
            soup = BeautifulSoup(content, "lxml")

            desc_el = soup.find("div", {"id": "jobDescriptionText"})
            if not desc_el:
                desc_el = soup.find("div", {"class": lambda c: c and "jobsearch-jobDescriptionText" in str(c)})
            if desc_el:
                return desc_el.get_text(separator="\n", strip=True)

        except Exception as e:
            logger.debug(f"Could not get description from {url}: {e}")

        return ""
