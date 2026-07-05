"""Scraper source — SCAFFOLD ONLY. Disabled by default.

⚠️  LEGAL / ToS WARNING
Scraping LinkedIn, Naukri, Glassdoor, Indeed and most other job boards violates their Terms of
Service, is actively blocked, and can carry legal and account-ban risk. This module exists ONLY
so the pluggable source architecture is complete and a compliant scraper can be dropped in later
(e.g. against a site you operate, or one whose ToS/robots you have verified permits it).

It stays disabled unless `MINDBRIDGE_ENABLE_SCRAPER=1`, and even then `fetch_jobs` raises
`NotImplementedError` because no actual scraping logic ships here. Implementing real scraping is a
deliberate, per-source decision the operator must make — not a default.
"""

from __future__ import annotations

from mindbridge.config import settings
from mindbridge.ingestion.base import JobSource
from mindbridge.schemas import JobPosting


class ScraperDisabledError(RuntimeError):
    """Raised when the scraper is invoked while disabled."""


class ScraperJobSource(JobSource):
    name = "scraper"

    def available(self) -> bool:
        return bool(settings.enable_scraper)

    def fetch_jobs(self, query: str = "", limit: int = 50) -> list[JobPosting]:
        if not self.available():
            raise ScraperDisabledError(
                "Scraper source is disabled. Scraping most job boards violates their Terms of "
                "Service. Set MINDBRIDGE_ENABLE_SCRAPER=1 only for a source you are authorized "
                "to scrape, then implement fetch_jobs() for that specific site."
            )
        raise NotImplementedError(
            "No scraping logic ships with MindBridge. Implement a compliant, per-source scraper "
            "here (respect robots.txt, rate limits, and the site's ToS)."
        )
