"""Shared data contracts for MindBridge.

Every layer — ingestion, parsing, features, matching — speaks in these three types, so the
components stay decoupled. Keep them small and typed; behavior lives elsewhere.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class JobPosting(BaseModel):
    """A single open role, normalized from whatever source produced it."""

    id: str
    title: str
    company: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)  # required / must-have skills
    preferred_skills: list[str] = Field(default_factory=list)  # nice-to-have skills
    min_experience: float = 0.0  # years
    max_experience: Optional[float] = None  # years; None = no ceiling
    location: str = ""
    remote: bool = False
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    source: str = "unknown"  # sample | api | scraper | demo | user | ...
    raw_text: str = ""  # original blob, kept for embedding + debugging

    @field_validator("skills", "preferred_skills", mode="before")
    @classmethod
    def _coerce_skills(cls, v: Any) -> list[str]:
        return _to_skill_list(v)

    def matchable_text(self) -> str:
        """The text stage-1 retrieval embeds for this job."""
        parts = [
            self.title,
            self.company,
            self.description,
            " ".join(self.skills),
            " ".join(self.preferred_skills),
            self.raw_text,
        ]
        return "\n".join(p for p in parts if p).strip()


class CandidateProfile(BaseModel):
    """A job seeker (hiree), typically built from a parsed resume."""

    id: str
    name: str = ""
    headline: str = ""  # e.g. "Senior Backend Engineer"
    skills: list[str] = Field(default_factory=list)
    years_experience: float = 0.0
    location: str = ""
    open_to_remote: bool = True
    desired_salary: Optional[float] = None
    resume_text: str = ""
    source: str = "unknown"

    @field_validator("skills", mode="before")
    @classmethod
    def _coerce_skills(cls, v: Any) -> list[str]:
        return _to_skill_list(v)

    def matchable_text(self) -> str:
        """The text stage-1 retrieval embeds for this candidate."""
        parts = [self.headline, " ".join(self.skills), self.resume_text]
        return "\n".join(p for p in parts if p).strip()


class MatchResult(BaseModel):
    """One ranked pairing. Direction-agnostic: `subject` is who we matched *for*,
    `matched` is the thing recommended to them.

    The value of the product is the *explanation*, so `reasons` and `feature_breakdown`
    are first-class, not afterthoughts.
    """

    subject_id: str  # the candidate (job-search) or job (candidate-search) we matched for
    matched_id: str  # the recommended job or candidate
    matched_label: str = ""  # human label, e.g. job title or candidate name
    score: float = 0.0  # final blended score in [0, 1]
    semantic_score: float = 0.0  # stage-1 cosine similarity in [0, 1]
    rerank_score: float = 0.0  # stage-2 score in [0, 1]
    reasons: list[str] = Field(default_factory=list)  # human-readable "why this match"
    feature_breakdown: dict[str, float] = Field(default_factory=dict)

    @field_validator("score", "semantic_score", "rerank_score")
    @classmethod
    def _clamp_unit(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


def _to_skill_list(v: Any) -> list[str]:
    """Accept a list, a comma/semicolon/pipe-separated string, or None → clean lowercase list."""
    if v is None:
        return []
    if isinstance(v, str):
        raw = v.replace(";", ",").replace("|", ",").split(",")
    elif isinstance(v, (list, tuple, set)):
        raw = list(v)
    else:
        return []
    seen: list[str] = []
    for item in raw:
        s = str(item).strip().lower()
        if s and s not in seen:
            seen.append(s)
    return seen
