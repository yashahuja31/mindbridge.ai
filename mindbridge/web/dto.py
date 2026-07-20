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


class ProviderOut(BaseModel):
    """One configured OAuth provider — the client renders a sign-in button per entry."""

    name: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    auth_provider: str = "password"
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


# ---- Profiles (hiree) ------------------------------------------------------------------------


class ProfileIn(BaseModel):
    """Create/update a hiree's persistent matching profile. All fields optional-ish: a bare
    `resume_text` is enough — skills/experience are auto-extracted server-side when omitted."""

    name: str = ""
    headline: str = ""
    skills: Optional[list[str]] = None  # None = extract from resume_text
    years_experience: Optional[float] = Field(default=None, ge=0, le=60)
    location: str = ""
    open_to_remote: bool = True
    desired_salary: Optional[float] = Field(default=None, ge=0)
    resume_text: str = ""


class ProfileOut(BaseModel):
    name: str
    headline: str
    skills: list[str]
    years_experience: float
    location: str
    open_to_remote: bool
    desired_salary: Optional[float]
    resume_text: str
    updated_at: datetime


class ProfileMatchRequest(BaseModel):
    """Run the hiree flow from the saved profile — no resume paste needed."""

    k: int = Field(default=10, ge=1, le=50)
    sources: Optional[list[str]] = None


# ---- Postings (hirer) ------------------------------------------------------------------------


class PostingIn(BaseModel):
    """Create/update one of a hirer's saved job postings."""

    title: str = Field(min_length=1, max_length=300)
    company: str = ""
    description: str = ""
    skills: Optional[list[str]] = None  # None = extract from description
    min_experience: float = Field(default=0.0, ge=0, le=60)
    max_experience: Optional[float] = Field(default=None, ge=0, le=60)
    location: str = ""
    remote: bool = False
    salary_min: Optional[float] = Field(default=None, ge=0)
    salary_max: Optional[float] = Field(default=None, ge=0)
    apply_url: Optional[str] = None


class PostingOut(BaseModel):
    id: int
    title: str
    company: str
    description: str
    skills: list[str]
    min_experience: float
    max_experience: Optional[float]
    location: str
    remote: bool
    salary_min: Optional[float]
    salary_max: Optional[float]
    apply_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PostingMatchRequest(BaseModel):
    """Run the hirer flow from a saved posting."""

    k: int = Field(default=10, ge=1, le=50)
    sources: Optional[list[str]] = None
