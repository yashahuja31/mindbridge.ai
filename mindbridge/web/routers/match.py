"""Matching routes — the product's core, exposed both directions plus resume upload and history.

    POST /match/jobs          hiree flow: resume text -> best jobs
    POST /match/jobs/upload    hiree flow: uploaded resume file -> best jobs
    POST /match/candidates     hirer flow: a job (id or pasted text) -> best candidates
    GET  /match/history        signed-in user's past runs

All matching endpoints work anonymously; when a valid token is present the run is also saved to
that user's history. Results are the engine's `MatchResult`s, explanations (`reasons`) included.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from mindbridge.parsing.resume_parser import parse_resume_bytes
from mindbridge.schemas import MatchResult
from mindbridge.web.db import get_db
from mindbridge.web.dto import MatchCandidatesRequest, MatchJobsRequest
from mindbridge.web.models import MatchHistory, User
from mindbridge.web.security import get_current_user, get_optional_user
from mindbridge.web import services

router = APIRouter(prefix="/match", tags=["match"])


def _maybe_save(db: Session, user: Optional[User], direction: str, summary: str, results):
    """Persist history only for signed-in callers; anonymous runs are stateless."""
    if user is not None:
        services.save_history(db, user, direction, summary, results)


@router.post("/jobs", response_model=list[MatchResult])
def match_jobs(
    body: MatchJobsRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> list[MatchResult]:
    results = services.match_jobs_for_resume(body.resume_text, k=body.k, sources=body.sources)
    _maybe_save(db, user, "jobs", f"Resume match -> {len(results)} jobs", results)
    return results


@router.post("/jobs/upload", response_model=list[MatchResult])
async def match_jobs_upload(
    file: UploadFile = File(...),
    k: int = Form(10),
    sources: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> list[MatchResult]:
    """Upload a resume (.txt/.md/.pdf/.docx) and get best-fit jobs. `sources` is comma-separated."""
    raw = await file.read()
    text = parse_resume_bytes(raw, file.filename or "")
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read any text from the uploaded file",
        )
    k = max(1, min(int(k), 50))
    src = [s for s in sources.split(",") if s] if sources else None
    results = services.match_jobs_for_resume(text, k=k, sources=src)
    _maybe_save(db, user, "jobs", f"Upload {file.filename} -> {len(results)} jobs", results)
    return results


@router.post("/candidates", response_model=list[MatchResult])
def match_candidates(
    body: MatchCandidatesRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> list[MatchResult]:
    if not body.job_id and not (body.job_text and body.job_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either job_id or job_text",
        )
    job = services.resolve_job(body.job_id, body.job_text, body.job_title, sources=body.sources)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No job found for id '{body.job_id}'",
        )
    results = services.match_candidates_for_job(job, k=body.k, sources=body.sources)
    _maybe_save(db, user, "candidates", f"{job.title} -> {len(results)} candidates", results)
    return results


@router.get("/history")
def match_history(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    """The signed-in user's saved runs, newest first, each with its full ranked results."""
    rows = (
        db.query(MatchHistory)
        .filter(MatchHistory.user_id == user.id)
        .order_by(MatchHistory.created_at.desc(), MatchHistory.id.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "direction": r.direction,
            "query_summary": r.query_summary,
            "result_count": r.result_count,
            "created_at": r.created_at.isoformat(),
            "results": json.loads(r.results_json or "[]"),
        }
        for r in rows
    ]
