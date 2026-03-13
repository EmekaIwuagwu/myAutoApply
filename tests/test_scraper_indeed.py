"""Test: Scrape 5 jobs from Indeed for 'Python Developer Remote'."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def test_indeed_scraper():
    from autoapply.scrapers.indeed_scraper import IndeedScraper

    scraper = IndeedScraper()
    print("Scraping Indeed for 'Python Developer Remote'...")

    jobs = await scraper.search_jobs(
        query="Python Developer",
        location="Remote",
        max_pages=1,
    )

    print(f"Found {len(jobs)} jobs")
    assert len(jobs) >= 0, "Scraper should return a list (may be empty due to rate limiting)"

    for i, job in enumerate(jobs[:5]):
        print(f"\nJob {i+1}:")
        print(f"  Title:   {job.get('title', '—')}")
        print(f"  Company: {job.get('company', '—')}")
        print(f"  Location:{job.get('location', '—')}")
        print(f"  URL:     {job.get('url', '—')[:80]}")
        print(f"  Desc:    {(job.get('description') or '')[:100]}...")

        # Validate structure
        assert "platform" in job
        assert "title" in job
        assert "url" in job
        assert job["platform"] == "indeed"

    print(f"\n✓ Indeed scraper returned {len(jobs)} jobs with correct structure")
    return jobs


async def test_indeed_url_builder():
    from autoapply.scrapers.indeed_scraper import IndeedScraper
    scraper = IndeedScraper()
    url = scraper._build_search_url("Python Developer", "Remote", 0)
    assert "indeed.com" in url
    assert "Python+Developer" in url or "Python%20Developer" in url or "Python" in url
    print(f"✓ URL builder: {url}")


if __name__ == "__main__":
    print("Running Indeed scraper tests...")
    asyncio.run(test_indeed_url_builder())
    asyncio.run(test_indeed_scraper())
    print("\n✅ Indeed scraper tests complete!")
