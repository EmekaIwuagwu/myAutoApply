import logging
from datetime import datetime
from typing import List, Dict
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..browser.playwright_engine import PlaywrightEngine
from ..browser.human_simulator import random_delay

logger = logging.getLogger(__name__)


class GreenhouseScraper:
    """Scraper for Greenhouse (boards.greenhouse.io) and Lever (jobs.lever.co) ATS forms."""

    def __init__(self, engine: PlaywrightEngine = None):
        self.engine = engine
        self._owns_engine = engine is None

    async def _get_engine(self) -> PlaywrightEngine:
        if not self.engine:
            self.engine = PlaywrightEngine()
            await self.engine.launch()
        return self.engine

    async def scrape_job_board(self, company_board_url: str) -> List[Dict]:
        """Scrape a company's Greenhouse job board."""
        engine = await self._get_engine()
        jobs = []

        try:
            page = await engine.navigate(company_board_url)
            await random_delay(1.5, 3.0)

            content = await engine.get_content(page)
            soup = BeautifulSoup(content, "lxml")

            # Greenhouse boards structure
            if "greenhouse.io" in company_board_url:
                jobs = self._parse_greenhouse_board(soup, company_board_url)
            elif "lever.co" in company_board_url:
                jobs = self._parse_lever_board(soup, company_board_url)

        except Exception as e:
            logger.error(f"Greenhouse/Lever scrape error: {e}")

        if self._owns_engine and self.engine:
            await self.engine.close()
            self.engine = None

        return jobs

    def _parse_greenhouse_board(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Parse Greenhouse job board listings."""
        jobs = []
        company = self._extract_company_from_url(base_url)

        sections = soup.find_all(["section", "div"], {"class": lambda c: c and "level-0" in str(c)})
        if not sections:
            sections = [soup]

        for section in sections:
            job_posts = section.find_all("div", {"class": "opening"})
            if not job_posts:
                job_posts = section.find_all(["li", "div"], {"class": lambda c: c and "job" in str(c).lower()})

            for post in job_posts:
                try:
                    job = self._parse_greenhouse_post(post, company, base_url)
                    if job.get("url") and job.get("title"):
                        jobs.append(job)
                except Exception as e:
                    logger.debug(f"Greenhouse post parse error: {e}")

        return jobs

    def _parse_greenhouse_post(self, post, company: str, base_url: str) -> Dict:
        """Parse a single Greenhouse job posting."""
        job = {
            "platform": "greenhouse",
            "title": "",
            "company": company,
            "location": "",
            "url": "",
            "salary_range": "",
            "posted_date": "",
            "description": "",
            "scraped_at": datetime.utcnow().isoformat(),
        }

        link = post.find("a")
        if link:
            job["title"] = link.get_text(strip=True)
            href = link.get("href", "")
            if href.startswith("http"):
                job["url"] = href
            elif href.startswith("/"):
                domain = "/".join(base_url.split("/")[:3])
                job["url"] = urljoin(domain, href)

        loc_el = post.find(["span", "div"], {"class": lambda c: c and "location" in str(c).lower()})
        if loc_el:
            job["location"] = loc_el.get_text(strip=True)

        return job

    def _parse_lever_board(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Parse Lever job board listings."""
        jobs = []
        company = self._extract_company_from_url(base_url)

        postings = soup.find_all("div", {"class": "posting"})
        if not postings:
            postings = soup.find_all("a", {"class": "posting-title"})

        for post in postings:
            try:
                job = {
                    "platform": "greenhouse",
                    "title": "",
                    "company": company,
                    "location": "",
                    "url": "",
                    "salary_range": "",
                    "posted_date": "",
                    "description": "",
                    "scraped_at": datetime.utcnow().isoformat(),
                }

                title_el = post.find("h5") or post.find(["h2", "h3"])
                if title_el:
                    job["title"] = title_el.get_text(strip=True)

                loc_el = post.find("span", {"class": "sort-by-location"})
                if loc_el:
                    job["location"] = loc_el.get_text(strip=True)

                link = post.find("a", {"class": "posting-title"}) or post.find("a")
                if link and link.get("href"):
                    href = link["href"]
                    job["url"] = href if href.startswith("http") else urljoin(base_url, href)

                if job["title"] and job["url"]:
                    jobs.append(job)

            except Exception as e:
                logger.debug(f"Lever post parse error: {e}")

        return jobs

    async def get_application_form_fields(self, job_url: str) -> List[Dict]:
        """Extract all form fields from a Greenhouse/Lever application form."""
        engine = await self._get_engine()
        fields = []

        try:
            page = await engine.navigate(job_url)
            await random_delay(1.5, 2.5)

            content = await engine.get_content(page)
            soup = BeautifulSoup(content, "lxml")

            form = soup.find("form", {"id": lambda i: i and "application" in str(i).lower()})
            if not form:
                form = soup.find("form")

            if form:
                fields = self._extract_form_fields(form)

        except Exception as e:
            logger.error(f"Form field extraction error: {e}")

        return fields

    def _extract_form_fields(self, form) -> List[Dict]:
        """Extract all form fields from a parsed form element."""
        fields = []

        for field_wrapper in form.find_all(["div", "li"], {"class": lambda c: c and "field" in str(c).lower()}):
            try:
                label_el = field_wrapper.find("label")
                label = label_el.get_text(strip=True) if label_el else ""

                input_el = (
                    field_wrapper.find("input")
                    or field_wrapper.find("textarea")
                    or field_wrapper.find("select")
                )

                if not input_el:
                    continue

                field = {
                    "label": label,
                    "name": input_el.get("name", ""),
                    "id": input_el.get("id", ""),
                    "type": input_el.get("type", input_el.name),
                    "placeholder": input_el.get("placeholder", ""),
                    "required": input_el.get("required") is not None or "required" in field_wrapper.get("class", []),
                    "options": [],
                }

                if input_el.name == "select":
                    field["options"] = [
                        opt.get_text(strip=True)
                        for opt in input_el.find_all("option")
                        if opt.get_text(strip=True)
                    ]

                fields.append(field)

            except Exception as e:
                logger.debug(f"Field extraction error: {e}")

        return fields

    def _extract_company_from_url(self, url: str) -> str:
        """Extract company name from board URL."""
        try:
            parts = url.rstrip("/").split("/")
            if "greenhouse.io" in url:
                # boards.greenhouse.io/companyname
                return parts[-1].replace("-", " ").title()
            elif "lever.co" in url:
                # jobs.lever.co/companyname
                return parts[-1].replace("-", " ").title()
        except Exception:
            pass
        return "Unknown Company"
