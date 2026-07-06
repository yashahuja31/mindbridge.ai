"""Build and load the parsed demo corpus.

The two demo zips hold 10k markdown files each. Parsing them on every process start is wasteful,
and extracting 20k loose files pollutes the tree — so we parse ONCE (reading straight from the
zip via `zipfile`) and cache the parsed domain objects under `data/processed/` (gitignored).

Cache format: parquet (columnar, fast) when pyarrow is available, else a JSONL fallback that
round-trips pydantic exactly with zero extra deps. Readers try parquet first, then JSONL, and
build the cache on demand if neither exists.

    build_corpus(force=False, limit=None) -> {"jobs": n, "candidates": n}
    load_cached_jobs()       -> list[JobPosting]
    load_cached_candidates() -> list[CandidateProfile]
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from mindbridge.config import JOBS_ZIP, PROCESSED_DIR, RESUMES_ZIP, settings
from mindbridge.parsing.demo_markdown import parse_job_markdown, parse_resume_markdown
from mindbridge.schemas import CandidateProfile, JobPosting

JOBS_PARQUET = PROCESSED_DIR / "jobs.parquet"
JOBS_JSONL = PROCESSED_DIR / "jobs.jsonl"
CANDS_PARQUET = PROCESSED_DIR / "candidates.parquet"
CANDS_JSONL = PROCESSED_DIR / "candidates.jsonl"


def _iter_zip_docs(zip_path: Path, limit: int | None):
    """Yield (stem, text) for each .md in a zip, sorted by name, up to `limit`."""
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".md"))
        if limit is not None:
            names = names[:limit]
        for name in names:
            yield Path(name).stem, zf.read(name).decode("utf-8", "ignore")


def _write_cache(models, parquet_path: Path, jsonl_path: Path) -> Path:
    """Write models to parquet (preferred) or JSONL. Returns the path actually written."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    records = [m.model_dump() for m in models]
    try:
        import pandas as pd

        pd.DataFrame(records).to_parquet(parquet_path, index=False)
        jsonl_path.unlink(missing_ok=True)  # avoid a stale fallback shadowing the fresh parquet
        return parquet_path
    except Exception:
        with jsonl_path.open("w", encoding="utf-8") as fh:
            for m in models:
                fh.write(m.model_dump_json() + "\n")
        parquet_path.unlink(missing_ok=True)
        return jsonl_path


def _coerce(value):
    """Normalize parquet-read values so pydantic validators see plain Python types."""
    # numpy arrays (list columns) -> list; numpy scalars -> python; pandas NA -> None.
    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        return value.tolist()
    try:
        import pandas as pd

        if not isinstance(value, (list, tuple, dict)) and pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _read_cache(parquet_path: Path, jsonl_path: Path, model_cls, limit: int | None):
    """Read a cache file back into validated pydantic models."""
    if parquet_path.exists():
        import pandas as pd

        df = pd.read_parquet(parquet_path)
        if limit is not None:
            df = df.head(limit)
        out = []
        for rec in df.to_dict(orient="records"):
            out.append(model_cls.model_validate({k: _coerce(v) for k, v in rec.items()}))
        return out
    if jsonl_path.exists():
        out = []
        with jsonl_path.open(encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if limit is not None and i >= limit:
                    break
                line = line.strip()
                if line:
                    out.append(model_cls.model_validate_json(line))
        return out
    return None


def corpus_cached() -> bool:
    return (JOBS_PARQUET.exists() or JOBS_JSONL.exists()) and (
        CANDS_PARQUET.exists() or CANDS_JSONL.exists()
    )


def build_corpus(force: bool = False, limit: int | None = None) -> dict[str, int]:
    """Parse both demo zips into the processed cache. Idempotent unless `force`."""
    if not force and corpus_cached():
        return {
            "jobs": len(load_cached_jobs()),
            "candidates": len(load_cached_candidates()),
            "rebuilt": 0,
        }
    if not JOBS_ZIP.exists() or not RESUMES_ZIP.exists():
        raise FileNotFoundError(
            f"Demo corpus zips not found. Expected:\n  {JOBS_ZIP}\n  {RESUMES_ZIP}"
        )

    jobs = [parse_job_markdown(text, stem) for stem, text in _iter_zip_docs(JOBS_ZIP, limit)]
    cands = [parse_resume_markdown(text, stem) for stem, text in _iter_zip_docs(RESUMES_ZIP, limit)]

    _write_cache(jobs, JOBS_PARQUET, JOBS_JSONL)
    _write_cache(cands, CANDS_PARQUET, CANDS_JSONL)
    return {"jobs": len(jobs), "candidates": len(cands), "rebuilt": 1}


def load_cached_jobs(limit: int | None = None) -> list[JobPosting]:
    """Load parsed demo jobs, building the cache first if absent. Honors settings.corpus_limit."""
    limit = settings.corpus_limit if limit is None else limit
    cached = _read_cache(JOBS_PARQUET, JOBS_JSONL, JobPosting, limit)
    if cached is None:
        build_corpus()
        cached = _read_cache(JOBS_PARQUET, JOBS_JSONL, JobPosting, limit)
    return cached or []


def load_cached_candidates(limit: int | None = None) -> list[CandidateProfile]:
    """Load parsed demo candidates, building the cache first if absent. Honors corpus_limit."""
    limit = settings.corpus_limit if limit is None else limit
    cached = _read_cache(CANDS_PARQUET, CANDS_JSONL, CandidateProfile, limit)
    if cached is None:
        build_corpus()
        cached = _read_cache(CANDS_PARQUET, CANDS_JSONL, CandidateProfile, limit)
    return cached or []
