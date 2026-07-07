"""Service layer — the glue between HTTP handlers and the matching engine.

Routers stay thin: they validate input and call one of these functions. Everything engine-facing
(building profiles from raw text, resolving a job, running the two-stage pipeline, persisting
history) lives here so the same logic is reusable and testable without the web layer.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from mindbridge.ingestion.registry import load_candidates, load_jobs
from mindbridge.matching.engine import MatchEngine
from mindbridge.parsing.text_clean import extract_skills, guess_years_experience
from mindbridge.schemas import CandidateProfile, JobPosting, MatchResult
from mindbridge.web.models import MatchHistory, User

# One engine per process. Holding it is cheap (the TF-IDF vocabulary is fit per request against the
# candidate corpus), and it caches the process-wide embedder + reranker choice.
_engine: MatchEngine | None = None


def get_engine() -> MatchEngine:
    global _engine
    if _engine is None:
        _engine = MatchEngine()
    return _engine


def engine_info() -> dict[str, str]:
    eng = get_engine()
    return {"embedder": eng.embedder_backend, "reranker": eng.reranker_backend}


def candidate_from_text(resume_text: str, cand_id: str = "web-candidate") -> CandidateProfile:
    """Build a CandidateProfile from raw resume text using the same heuristics as the CLI."""
    return CandidateProfile(
        id=cand_id,
        name="",
        skills=extract_skills(resume_text),
        years_experience=guess_years_experience(resume_text),
        resume_text=resume_text,
        source="web",
    )


def job_from_text(job_text: str, title: str = "", job_id: str = "web-job") -> JobPosting:
    """Build a JobPosting from a pasted job description."""
    return JobPosting(
        id=job_id,
        title=title or "Posted role",
        description=job_text,
        skills=extract_skills(job_text),
        source="web",
        raw_text=job_text,
    )


def match_jobs_for_resume(
    resume_text: str, k: int = 10, sources: Optional[list[str]] = None
) -> list[MatchResult]:
    """Hiree flow: rank the available jobs for a resume."""
    candidate = candidate_from_text(resume_text)
    jobs = load_jobs(sources=sources)
    return get_engine().match_jobs_for_candidate(candidate, jobs, k=k)


def resolve_job(
    job_id: Optional[str],
    job_text: Optional[str],
    job_title: str = "",
    sources: Optional[list[str]] = None,
) -> Optional[JobPosting]:
    """Find a job by id among the sources, or synthesize one from pasted text. None if neither
    yields a job (caller turns that into a 400/404)."""
    if job_id:
        for job in load_jobs(sources=sources):
            if job.id == job_id:
                return job
        return None
    if job_text and job_text.strip():
        return job_from_text(job_text, title=job_title)
    return None


def match_candidates_for_job(
    job: JobPosting, k: int = 10, sources: Optional[list[str]] = None
) -> list[MatchResult]:
    """Hirer flow: rank the candidate corpus for a job."""
    candidates = load_candidates(sources=sources)
    return get_engine().match_candidates_for_job(job, candidates, k=k)


def save_history(
    db: Session,
    user: User,
    direction: str,
    query_summary: str,
    results: list[MatchResult],
) -> MatchHistory:
    """Persist a completed run for a signed-in user. Results are stored as JSON text."""
    record = MatchHistory(
        user_id=user.id,
        direction=direction,
        query_summary=query_summary[:500],
        result_count=len(results),
        results_json=json.dumps([r.model_dump() for r in results]),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
