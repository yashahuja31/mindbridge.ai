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
MODELS_DIR = PROJECT_ROOT / "models"


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
    w_semantic: float = 0.45
    w_skills: float = 0.30
    w_experience: float = 0.12
    w_location: float = 0.08
    w_salary: float = 0.05

    # How many candidates stage-1 retrieval passes to stage-2 before final top-k.
    retrieve_multiplier: int = 5


def _load() -> Settings:
    """Build settings, honoring the MINDBRIDGE_-prefixed env vars used in `.env.example`."""
    import os

    s = Settings()
    if os.getenv("MINDBRIDGE_ENABLE_SCRAPER") is not None:
        s.enable_scraper = os.getenv("MINDBRIDGE_ENABLE_SCRAPER", "0") in ("1", "true", "True")
    if os.getenv("MINDBRIDGE_EMBED_MODEL"):
        s.embed_model = os.getenv("MINDBRIDGE_EMBED_MODEL", s.embed_model)
    return s


settings = _load()
