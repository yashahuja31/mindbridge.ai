"""Central configuration, loaded from environment / a local `.env` file.

Nothing here is secret by default — real keys live in `.env` (gitignored). Import the singleton
`settings` anywhere you need a tunable value so there's one source of truth.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (mindbridge/config.py -> mindbridge/ -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
PROCESSED_DIR = DATA_DIR / "processed"  # parsed corpus cache (parquet/jsonl), gitignored
VECTORS_DIR = PROCESSED_DIR / "vectors"  # persisted stage-1 embeddings (M4), gitignored
MODELS_DIR = PROJECT_ROOT / "models"

# The two demo corpora (10k each) the user dropped in the repo root. Read straight from the
# zip — we never extract 20k loose files.
RESUMES_ZIP = PROJECT_ROOT / "demo_resumes_10000.zip"
JOBS_ZIP = PROJECT_ROOT / "demo_job_descriptions_10000.zip"


class Settings(BaseSettings):
    """Runtime settings. Env vars take precedence over these defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Embeddings ---
    # sentence-transformers model. If it can't be loaded (offline / no torch), the embedder
    # transparently falls back to TF-IDF so the pipeline always runs.
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Official job APIs (Adzuna) ---
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_country: str = "gb"

    # --- Scraper adapter ---
    # Scraping most job boards violates their Terms of Service. This flag only exists so the
    # pluggable source architecture is complete; it is OFF unless explicitly set to 1.
    # Note the env var is prefixed MINDBRIDGE_ (see env_prefix override below via alias).
    enable_scraper: bool = False

    # --- Matching weights (stage-2 heuristic reranker) ---
    # These sum-weight the structured features + semantic score. Tune freely; they must be
    # non-negative. `train_reranker.py` replaces this hand-tuned blend with a learned model.
    # Rebalanced for the demo corpus: role + skills dominate because the corpus carries no
    # experience or salary signal, and role is the strongest real signal in the data.
    w_semantic: float = 0.35
    w_skills: float = 0.25
    w_role: float = 0.22
    w_experience: float = 0.08
    w_location: float = 0.06
    w_salary: float = 0.04

    # How many candidates stage-1 retrieval passes to stage-2 before final top-k.
    retrieve_multiplier: int = 5

    # --- Web backend (M2) ---
    # Override the secret in production via MINDBRIDGE_SECRET_KEY / .env.
    secret_key: str = "dev-insecure-change-me-in-production"
    access_token_expire_minutes: int = 1440  # 24h
    database_url: str = f"sqlite:///{(DATA_DIR / 'mindbridge.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Cap how many corpus docs to load (per side). None = all 10k. Handy for dev/CI:
    # set MINDBRIDGE_CORPUS_LIMIT=200 for a fast-starting server / test suite.
    corpus_limit: int | None = None

    # --- Vector store (M4) ---
    # Persist stage-1 corpus embeddings under data/processed/vectors/ so a warm start skips
    # re-encoding the whole corpus. OFF for ad-hoc CLI runs by default is unnecessary — the
    # store keys entries by (backend, corpus fingerprint), so a stale cache can never be
    # served; disable only if you want zero disk writes (MINDBRIDGE_VECTOR_STORE=0).
    vector_store: bool = True

    # --- OAuth sign-in (Google / GitHub) ---
    # A provider is enabled simply by setting its client id + secret (env: GOOGLE_CLIENT_ID,
    # GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET). No keys = the provider
    # doesn't appear in GET /auth/providers and the SPA shows no button — password auth always works.
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    # Where the SPA lives — OAuth callbacks redirect the browser back here with our token.
    frontend_url: str = "http://localhost:5173"
    # Public base URL of this API, used to build the OAuth redirect URIs registered with the
    # provider (e.g. https://api.example.com in production).
    api_base_url: str = "http://127.0.0.1:8000"


def _load() -> Settings:
    """Build settings, honoring the MINDBRIDGE_-prefixed env vars used in `.env.example`."""
    import os

    s = Settings()
    if os.getenv("MINDBRIDGE_ENABLE_SCRAPER") is not None:
        s.enable_scraper = os.getenv("MINDBRIDGE_ENABLE_SCRAPER", "0") in ("1", "true", "True")
    if os.getenv("MINDBRIDGE_EMBED_MODEL"):
        s.embed_model = os.getenv("MINDBRIDGE_EMBED_MODEL", s.embed_model)
    if os.getenv("MINDBRIDGE_SECRET_KEY"):
        s.secret_key = os.getenv("MINDBRIDGE_SECRET_KEY", s.secret_key)
    if os.getenv("MINDBRIDGE_CORPUS_LIMIT"):
        try:
            s.corpus_limit = int(os.environ["MINDBRIDGE_CORPUS_LIMIT"])
        except ValueError:
            pass
    if os.getenv("MINDBRIDGE_VECTOR_STORE") is not None:
        s.vector_store = os.getenv("MINDBRIDGE_VECTOR_STORE", "1") in ("1", "true", "True")
    return s


settings = _load()
