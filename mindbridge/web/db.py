"""SQLAlchemy engine, session factory, and the FastAPI DB dependency.

One SQLite database (path from `settings.database_url`) holds users and match history — the
persistence M2 adds on top of the stateless engine. Kept deliberately small: a single engine,
a `SessionLocal` factory, `init_db()` to create tables, and `get_db()` for dependency injection.
Tests override `get_db` with a throwaway database, so nothing here hard-codes the prod DB.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from mindbridge.config import DATA_DIR, settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def make_engine(url: str | None = None):
    """Build an engine for `url` (defaults to the configured database). SQLite needs
    `check_same_thread=False` so the connection can be shared across FastAPI's threadpool."""
    url = url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


# Module-level engine + session factory bound to the configured database.
engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables. Idempotent — safe to call on every startup. The sqlite file lives
    under data/ (gitignored); ensure the directory exists first."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Import models so they register on Base.metadata before create_all.
    from mindbridge.web import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that's always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
