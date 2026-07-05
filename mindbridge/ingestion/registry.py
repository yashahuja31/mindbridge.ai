"""Source registry — the one place that knows which sources exist and merges their output.

Callers use `load_jobs(...)` / `load_candidates(...)` and never touch individual sources. Pass
`sources=["sample", "api"]` to pick; omit it to use every *available* source (sample always,
api only if keys are set, scraper only if explicitly enabled).
"""

from __future__ import annotations

from mindbridge.config import settings
from mindbridge.ingestion.api_source import AdzunaJobSource
from mindbridge.ingestion.sample_source import SampleJobSource, SampleResumeSource
from mindbridge.ingestion.scraper_source import ScraperJobSource
from mindbridge.schemas import CandidateProfile, JobPosting

# name -> factory. Adding a new source is a one-line change here.
_JOB_SOURCES = {
    "sample": SampleJobSource,
    "api": AdzunaJobSource,
    "scraper": ScraperJobSource,
}
_RESUME_SOURCES = {
    "sample": SampleResumeSource,
}


def _default_job_sources() -> list[str]:
    names = ["sample"]
    if settings.adzuna_app_id and settings.adzuna_app_key:
        names.append("api")
    if settings.enable_scraper:
        names.append("scraper")
    return names


def load_jobs(
    query: str = "", sources: list[str] | None = None, limit_per_source: int = 100
) -> list[JobPosting]:
    """Fetch and merge jobs from the requested (or all available) sources.

    De-duplicates by id. A failing source is skipped, never fatal.
    """
    names = sources if sources is not None else _default_job_sources()
    merged: dict[str, JobPosting] = {}
    for name in names:
        factory = _JOB_SOURCES.get(name)
        if factory is None:
            continue
        try:
            for job in factory().fetch_jobs(query=query, limit=limit_per_source):
                merged.setdefault(job.id, job)
        except Exception:
            # e.g. scraper disabled, API down — contribute nothing rather than break the pipeline.
            continue
    return list(merged.values())


def load_candidates(
    query: str = "", sources: list[str] | None = None, limit_per_source: int = 100
) -> list[CandidateProfile]:
    """Fetch and merge candidate profiles. Currently only the sample source produces these;
    live candidate ingestion (uploaded resume folders) arrives with the web layer."""
    names = sources if sources is not None else ["sample"]
    merged: dict[str, CandidateProfile] = {}
    for name in names:
        factory = _RESUME_SOURCES.get(name)
        if factory is None:
            continue
        try:
            for cand in factory().fetch_candidates(query=query, limit=limit_per_source):
                merged.setdefault(cand.id, cand)
        except Exception:
            continue
    return list(merged.values())
