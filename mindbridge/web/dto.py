"""Request/response models for the HTTP API.

These are the *web* contract and are kept separate from the engine's core schemas
(`JobPosting`/`CandidateProfile`/`MatchResult`) so the API can evolve without perturbing the
engine. `MatchResult` is reused verbatim in responses — it's already the shape the UI wants.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# ---- Auth ----------------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    role: str = "hiree"

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email")
        return v

    @field_validator("role")
    @classmethod
    def _role_allowed(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in ("hiree", "hirer"):
            raise ValueError("role must be 'hiree' or 'hirer'")
        return v


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---- Matching ------------------------------------------------------------------------------


class MatchJobsRequest(BaseModel):
    """Hiree flow: paste resume text, get best-fit jobs."""

    resume_text: str = Field(min_length=1)
    k: int = Field(default=10, ge=1, le=50)
    sources: Optional[list[str]] = None  # None = all available; e.g. ["sample"] for a fast demo


class MatchCandidatesRequest(BaseModel):
    """Hirer flow: identify a job (by id from the sources, or by pasted text) and get best-fit
    candidates from the resume corpus."""

    job_id: Optional[str] = None
    job_text: Optional[str] = None  # free-text JD when there's no id
    job_title: str = ""  # helps role-matching when pasting text
    k: int = Field(default=10, ge=1, le=50)
    sources: Optional[list[str]] = None

    @field_validator("job_text")
    @classmethod
    def _need_one(cls, v, info):
        return v


class HistoryOut(BaseModel):
    id: int
    direction: str
    query_summary: str
    result_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
