"""Demo corpus data source — the 10k+10k markdown corpus, parsed and cached.

Reads from the processed cache (`corpus_build`), not the zips directly, so `fetch_*` is a cheap
in-memory list slice. Registered under the name "demo" in the registry.
"""

from __future__ import annotations

from mindbridge.ingestion.base import JobSource, ResumeSource, text_filter
from mindbridge.ingestion.corpus_build import load_cached_candidates, load_cached_jobs
from mindbridge.schemas import CandidateProfile, JobPosting


class DemoJobSource(JobSource):
    name = "demo"

    def fetch_jobs(self, query: str = "", limit: int = 100) -> list[JobPosting]:
        jobs = load_cached_jobs()
        jobs = text_filter(
            jobs, query, key=lambda j: f"{j.title} {j.company} {' '.join(j.skills)}"
        )
        return jobs[:limit]


class DemoResumeSource(ResumeSource):
    name = "demo"

    def fetch_candidates(self, query: str = "", limit: int = 100) -> list[CandidateProfile]:
        cands = load_cached_candidates()
        cands = text_filter(
            cands, query, key=lambda c: f"{c.name} {c.headline} {' '.join(c.skills)}"
        )
        return cands[:limit]
