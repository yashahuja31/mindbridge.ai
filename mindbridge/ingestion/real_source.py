"""Real live job source — zero-config open API source.

Fetches live software engineering, AI, product, data, and design jobs with real apply links
from public job APIs (RemoteOK). Works with no API keys required and degrades gracefully if offline.
"""

from __future__ import annotations

from typing import Any

from mindbridge.ingestion.base import JobSource, text_filter
from mindbridge.parsing.text_clean import extract_skills
from mindbridge.schemas import JobPosting

REMOTEOK_API_URL = "https://remoteok.com/api"


class RealJobSource(JobSource):
    name = "real"

    def fetch_jobs(self, query: str = "", limit: int = 100) -> list[JobPosting]:
        try:
            import requests
        except ImportError:  # pragma: no cover
            return []

        try:
            headers = {"User-Agent": "MindBridge.ai Job Search/1.0"}
            resp = requests.get(REMOTEOK_API_URL, headers=headers, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
        except Exception:
            # Network or API failure should contribute nothing without crashing
            return []

        jobs: list[JobPosting] = []
        for item in payload:
            if not isinstance(item, dict) or not item.get("position"):
                continue

            title = str(item.get("position", "")).strip()
            company = str(item.get("company", "")).strip()
            desc = str(item.get("description", "") or "").strip()
            apply_url = item.get("url") or item.get("apply_url") or item.get("url_canonical")

            tags = item.get("tags") or []
            if isinstance(tags, list):
                skills = [str(t).lower().strip() for t in tags if t]
            else:
                skills = extract_skills(f"{title} {desc}")
            if not skills:
                skills = extract_skills(f"{title} {desc}")

            salary_min = None
            salary_max = None
            if item.get("salary_min"):
                try:
                    salary_min = float(item["salary_min"])
                except (ValueError, TypeError):
                    pass
            if item.get("salary_max"):
                try:
                    salary_max = float(item["salary_max"])
                except (ValueError, TypeError):
                    pass

            location = str(item.get("location") or "Remote").strip()

            jobs.append(
                JobPosting(
                    id=f"real-{item.get('id', len(jobs))}",
                    title=title,
                    company=company,
                    description=desc,
                    skills=skills,
                    location=location,
                    remote=True,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    source=self.name,
                    apply_url=apply_url,
                    raw_text=f"{title} {company} {desc}",
                )
            )

        jobs = text_filter(
            jobs, query, key=lambda j: f"{j.title} {j.company} {j.description} {' '.join(j.skills)}"
        )
        return jobs[:limit]
