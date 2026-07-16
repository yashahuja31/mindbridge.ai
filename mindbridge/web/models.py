"""ORM models — what the web layer persists beyond the stateless engine.

* `User`  — an account (hiree or hirer) with a bcrypt-hashed password.
* `Profile` — a hiree's saved matching profile (resume text + the structured fields the engine
  scores on). One per user; lets matching run with one click instead of re-pasting a resume.
* `Posting` — a hirer's saved job posting, the mirror image of `Profile` for the other side.
* `MatchHistory` — a saved run: which direction, a short human summary of the query, and the full
  ranked results as JSON. Lets a signed-in user revisit past searches; also the seed of the
  outcome-label data M5 will eventually learn from (a `label`/`hired` column drops in here later).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mindbridge.web.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    # NULL for accounts created via OAuth (Google/GitHub) — they have no local password and
    # password login is rejected for them until they set one.
    hashed_password: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # "password", "google", or "github" — how the account was created. Informational (shown in
    # the UI, useful for support); login is by whatever method currently works for the account.
    auth_provider: Mapped[str] = mapped_column(String(20), default="password", nullable=False)
    # "hiree" (job seeker) or "hirer" (employer). Not enforced as an enum at the DB level so the
    # taxonomy can grow without a migration; validated at the API boundary.
    role: Mapped[str] = mapped_column(String(20), default="hiree", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    history: Mapped[list["MatchHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    postings: Mapped[list["Posting"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Profile(Base):
    """A hiree's persistent matching profile — the fields `CandidateProfile` scores on, plus the
    raw resume text. Skills are stored as JSON text (portable across SQLite/Postgres)."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    headline: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    years_experience: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    open_to_remote: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    desired_salary: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class Posting(Base):
    """A hirer's saved job posting — the mirror of `Profile`: the fields `JobPosting` scores on.
    A hirer can keep several open roles and match candidates against any of them."""

    __tablename__ = "postings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    company: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    min_experience: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_experience: Mapped[float | None] = mapped_column(Float, nullable=True)
    location: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="postings")


class MatchHistory(Base):
    __tablename__ = "match_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    # "jobs" = matched jobs for a candidate (hiree flow); "candidates" = matched candidates for a
    # job (hirer flow).
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    query_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Full ranked MatchResult[] serialized as JSON text — portable across SQLite/Postgres.
    results_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="history")
