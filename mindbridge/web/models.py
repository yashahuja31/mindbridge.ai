"""ORM models — the two things M2 persists beyond the stateless engine.

* `User`  — an account (hiree or hirer) with a bcrypt-hashed password.
* `MatchHistory` — a saved run: which direction, a short human summary of the query, and the full
  ranked results as JSON. Lets a signed-in user revisit past searches; also the seed of the
  outcome-label data M5 will eventually learn from (a `label`/`hired` column drops in here later).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mindbridge.web.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    # "hiree" (job seeker) or "hirer" (employer). Not enforced as an enum at the DB level so the
    # taxonomy can grow without a migration; validated at the API boundary.
    role: Mapped[str] = mapped_column(String(20), default="hiree", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    history: Mapped[list["MatchHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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
