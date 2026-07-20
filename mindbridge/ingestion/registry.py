"""Source registry — the one place that knows which sources exist and merges their output.

Callers use `load_jobs(...)` / `load_candidates(...)` and never touch individual sources. Pass
`sources=["sample", "api"]` to pick; omit it to use every *available* source (sample always,
api only if keys are set, scraper only if explicitly enabled).
"""

from __future__ import annotations

from mindbridge.config import JOBS_ZIP, RESUMES_ZIP, settings
from mindbridge.ingestion.api_source import AdzunaJobSource
from mindbridge.ingestion.corpus_build import corpus_cached
from mindbridge.ingestion.demo_source import DemoJobSource, DemoResumeSource
from mindbridge.ingestion.real_source import RealJobSource
from mindbridge.ingestion.sample_source import SampleJobSource, SampleResumeSource
from mindbridge.ingestion.scraper_source import ScraperJobSource
from mindbridge.schemas import CandidateProfile, JobPosting

# name -> factory. Adding a new source is a one-line change here.
_JOB_SOURCES = {
    "sample": SampleJobSource,
    "real": RealJobSource,
    "demo": DemoJobSource,
    "api": AdzunaJobSource,
    "scraper": ScraperJobSource,
}
_RESUME_SOURCES = {
    "sample": SampleResumeSource,
    "demo": DemoResumeSource,
}


def _demo_available() -> bool:
    """The demo source is usable if the parsed cache exists or the zips are present to build it."""
    return corpus_cached() or (JOBS_ZIP.exists() and RESUMES_ZIP.exists())


def _default_job_sources() -> list[str]:
    names = ["sample", "real"]
    if _demo_available():
        names.append("demo")
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
    """Fetch and merge candidate profiles from the sample set plus the demo corpus when built."""
    if sources is not None:
        names = sources
    else:
        names = ["sample"] + (["demo"] if _demo_available() else [])
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
