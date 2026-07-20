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
from mindbridge.web.models import MatchHistory, Posting, Profile, User

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
    return match_jobs_for_candidate(candidate_from_text(resume_text), k=k, sources=sources)


def match_jobs_for_candidate(
    candidate: CandidateProfile, k: int = 10, sources: Optional[list[str]] = None
) -> list[MatchResult]:
    """Hiree flow for an already-built profile (pasted, uploaded, or saved)."""
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


# ---- Profiles & postings (persistent M3 entities) --------------------------------------------
#
# A `Profile` row is the persistent form of the engine's `CandidateProfile`; a `Posting` row is
# the persistent `JobPosting`. The `*_to_*` converters below are the only place that mapping
# lives, so the engine schemas stay the single matching contract.


def upsert_profile(db: Session, user: User, data: dict) -> Profile:
    """Create or update the user's (single) profile. `skills=None` means auto-extract from the
    resume text — same heuristic the paste/upload flows use, so saved and ad-hoc matching agree."""
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)

    resume_text = data.get("resume_text") or ""
    skills = data.get("skills")
    if skills is None:
        skills = extract_skills(f"{data.get('headline') or ''}\n{resume_text}")
    years = data.get("years_experience")
    if years is None:
        years = guess_years_experience(resume_text)

    profile.name = data.get("name") or ""
    profile.headline = data.get("headline") or ""
    profile.skills_json = json.dumps(list(skills))
    profile.years_experience = float(years)
    profile.location = data.get("location") or ""
    profile.open_to_remote = bool(data.get("open_to_remote", True))
    profile.desired_salary = data.get("desired_salary")
    profile.resume_text = resume_text
    db.commit()
    db.refresh(profile)
    return profile


def profile_to_candidate(profile: Profile) -> CandidateProfile:
    """The saved row → the engine's matching contract."""
    return CandidateProfile(
        id=f"user-{profile.user_id}",
        name=profile.name,
        headline=profile.headline,
        skills=json.loads(profile.skills_json or "[]"),
        years_experience=profile.years_experience,
        location=profile.location,
        open_to_remote=profile.open_to_remote,
        desired_salary=profile.desired_salary,
        resume_text=profile.resume_text,
        source="user",
    )


def profile_out(profile: Profile) -> dict:
    """Serialize a Profile row for the API (skills decoded from JSON)."""
    return {
        "name": profile.name,
        "headline": profile.headline,
        "skills": json.loads(profile.skills_json or "[]"),
        "years_experience": profile.years_experience,
        "location": profile.location,
        "open_to_remote": profile.open_to_remote,
        "desired_salary": profile.desired_salary,
        "resume_text": profile.resume_text,
        "updated_at": profile.updated_at,
    }


def apply_posting(posting: Posting, data: dict) -> None:
    """Copy validated PostingIn fields onto a Posting row. `skills=None` = extract from text."""
    skills = data.get("skills")
    if skills is None:
        skills = extract_skills(f"{data.get('title') or ''}\n{data.get('description') or ''}")
    posting.title = data.get("title") or ""
    posting.company = data.get("company") or ""
    posting.description = data.get("description") or ""
    posting.skills_json = json.dumps(list(skills))
    posting.min_experience = float(data.get("min_experience") or 0.0)
    posting.max_experience = data.get("max_experience")
    posting.location = data.get("location") or ""
    posting.remote = bool(data.get("remote", False))
    posting.salary_min = data.get("salary_min")
    posting.salary_max = data.get("salary_max")
    posting.apply_url = data.get("apply_url")


def posting_to_job(posting: Posting) -> JobPosting:
    """The saved row → the engine's matching contract."""
    return JobPosting(
        id=f"posting-{posting.id}",
        title=posting.title,
        company=posting.company,
        description=posting.description,
        skills=json.loads(posting.skills_json or "[]"),
        min_experience=posting.min_experience,
        max_experience=posting.max_experience,
        location=posting.location,
        remote=posting.remote,
        salary_min=posting.salary_min,
        salary_max=posting.salary_max,
        source="user",
        apply_url=posting.apply_url,
        raw_text=posting.description,
    )


def posting_out(posting: Posting) -> dict:
    """Serialize a Posting row for the API (skills decoded from JSON)."""
    return {
        "id": posting.id,
        "title": posting.title,
        "company": posting.company,
        "description": posting.description,
        "skills": json.loads(posting.skills_json or "[]"),
        "min_experience": posting.min_experience,
        "max_experience": posting.max_experience,
        "location": posting.location,
        "remote": posting.remote,
        "salary_min": posting.salary_min,
        "salary_max": posting.salary_max,
        "apply_url": posting.apply_url,
        "created_at": posting.created_at,
        "updated_at": posting.updated_at,
    }
