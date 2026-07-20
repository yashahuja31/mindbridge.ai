"""Official job API source — Adzuna adapter (free tier, sanctioned).

Register at https://developer.adzuna.com/ for an app id + key, put them in `.env`, and this
source starts returning live jobs. With no keys configured it degrades gracefully to an empty
list (and says so via `available()`), so it never breaks an offline run.

Adzuna is used because it has a documented free API. Other sanctioned APIs (USAJobs, etc.) can
be added as sibling classes implementing the same `JobSource` interface.
"""

from __future__ import annotations

from typing import Any

from mindbridge.config import settings
from mindbridge.ingestion.base import JobSource
from mindbridge.parsing.text_clean import extract_skills
from mindbridge.schemas import JobPosting

ADZUNA_ENDPOINT = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaJobSource(JobSource):
    name = "api"

    def __init__(self) -> None:
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.country = settings.adzuna_country or "in"

    def available(self) -> bool:
        return bool(self.app_id and self.app_key)

    def fetch_jobs(self, query: str = "", limit: int = 500) -> list[JobPosting]:
        if not self.available():
            # No keys -> stay quiet and let other sources carry the run.
            return []
        try:
            import requests
        except ImportError:  # pragma: no cover
            return []

        params: dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": min(limit, 50),
            "what": query or "",
            "content-type": "application/json",
        }
        url = ADZUNA_ENDPOINT.format(country=self.country)
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            # Network/API errors must never crash matching; just contribute nothing.
            return []

        jobs: list[JobPosting] = []
        for item in payload.get("results", [])[:limit]:
            desc = item.get("description", "") or ""
            jobs.append(
                JobPosting(
                    id=f"adzuna-{item.get('id', len(jobs))}",
                    title=item.get("title", ""),
                    company=(item.get("company") or {}).get("display_name", ""),
                    description=desc,
                    skills=extract_skills(desc),
                    location=(item.get("location") or {}).get("display_name", ""),
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    source=self.name,
                    apply_url=item.get("redirect_url") or item.get("url"),
                    raw_text=desc,
                )
            )
        return jobs
