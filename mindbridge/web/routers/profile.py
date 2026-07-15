"""Profile & posting routes — the persistent side of M3.

Hiree side (one profile per user):
    GET    /profile              the saved profile (404 until one exists)
    PUT    /profile              create/update it (skills auto-extracted when omitted)
    DELETE /profile              remove it
    POST   /profile/match        hiree flow from the saved profile — no re-pasting

Hirer side (many postings per user):
    GET    /postings             the user's saved postings
    POST   /postings             create one
    GET    /postings/{id}        fetch one
    PUT    /postings/{id}        update one
    DELETE /postings/{id}        remove one
    POST   /postings/{id}/match  hirer flow from the saved posting

All routes require auth — profiles/postings are inherently owned. Match runs from saved entities
are persisted to history like any other signed-in run.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from mindbridge.schemas import MatchResult
from mindbridge.web.db import get_db
from mindbridge.web.dto import (
    PostingIn,
    PostingMatchRequest,
    PostingOut,
    ProfileIn,
    ProfileMatchRequest,
    ProfileOut,
)
from mindbridge.web.models import Posting, Profile, User
from mindbridge.web.security import get_current_user
from mindbridge.web import services

router = APIRouter(tags=["profile"])


# ---- Hiree profile ---------------------------------------------------------------------------


def _get_profile_or_404(db: Session, user: User) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile yet — create one with PUT /profile",
        )
    return profile


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    return services.profile_out(_get_profile_or_404(db, user))


@router.put("/profile", response_model=ProfileOut)
def put_profile(
    body: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Create or update the signed-in user's profile (idempotent upsert)."""
    profile = services.upsert_profile(db, user, body.model_dump())
    return services.profile_out(profile)


@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> None:
    db.delete(_get_profile_or_404(db, user))
    db.commit()


@router.post("/profile/match", response_model=list[MatchResult])
def match_from_profile(
    body: ProfileMatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MatchResult]:
    """One-click hiree flow: rank jobs against the saved profile."""
    profile = _get_profile_or_404(db, user)
    candidate = services.profile_to_candidate(profile)
    if not candidate.matchable_text():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile is empty — add a resume, headline, or skills first",
        )
    results = services.match_jobs_for_candidate(candidate, k=body.k, sources=body.sources)
    services.save_history(db, user, "jobs", f"Profile match -> {len(results)} jobs", results)
    return results


# ---- Hirer postings --------------------------------------------------------------------------


def _get_posting_or_404(db: Session, user: User, posting_id: int) -> Posting:
    posting = (
        db.query(Posting)
        .filter(Posting.id == posting_id, Posting.user_id == user.id)
        .first()
    )
    if posting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No posting with id {posting_id}"
        )
    return posting


@router.get("/postings", response_model=list[PostingOut])
def list_postings(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[dict]:
    rows = (
        db.query(Posting)
        .filter(Posting.user_id == user.id)
        .order_by(Posting.created_at.desc(), Posting.id.desc())
        .all()
    )
    return [services.posting_out(p) for p in rows]


@router.post("/postings", response_model=PostingOut, status_code=status.HTTP_201_CREATED)
def create_posting(
    body: PostingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    posting = Posting(user_id=user.id)
    services.apply_posting(posting, body.model_dump())
    db.add(posting)
    db.commit()
    db.refresh(posting)
    return services.posting_out(posting)


@router.get("/postings/{posting_id}", response_model=PostingOut)
def get_posting(
    posting_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    return services.posting_out(_get_posting_or_404(db, user, posting_id))


@router.put("/postings/{posting_id}", response_model=PostingOut)
def update_posting(
    posting_id: int,
    body: PostingIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    posting = _get_posting_or_404(db, user, posting_id)
    services.apply_posting(posting, body.model_dump())
    db.commit()
    db.refresh(posting)
    return services.posting_out(posting)


@router.delete("/postings/{posting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_posting(
    posting_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    db.delete(_get_posting_or_404(db, user, posting_id))
    db.commit()


@router.post("/postings/{posting_id}/match", response_model=list[MatchResult])
def match_from_posting(
    posting_id: int,
    body: PostingMatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MatchResult]:
    """One-click hirer flow: rank the candidate corpus against a saved posting."""
    posting = _get_posting_or_404(db, user, posting_id)
    job = services.posting_to_job(posting)
    results = services.match_candidates_for_job(job, k=body.k, sources=body.sources)
    services.save_history(
        db, user, "candidates", f"{job.title} -> {len(results)} candidates", results
    )
    return results
