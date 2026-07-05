"""Sample data source — fully implemented, offline, no API keys.

Reads the committed demo set in `data/sample/`:
  - jobs.csv          : one row per job posting
  - resumes/*.txt     : one plain-text resume per file
  - candidates.csv    : optional metadata (name, location, years) keyed by resume filename

This is what guarantees the whole pipeline runs on a fresh clone.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from mindbridge.config import SAMPLE_DIR
from mindbridge.ingestion.base import JobSource, ResumeSource
from mindbridge.parsing.resume_parser import parse_resume_file
from mindbridge.parsing.text_clean import extract_skills, guess_years_experience
from mindbridge.schemas import CandidateProfile, JobPosting


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class SampleJobSource(JobSource):
    name = "sample"

    def __init__(self, root: Path = SAMPLE_DIR) -> None:
        self.jobs_csv = root / "jobs.csv"

    def fetch_jobs(self, query: str = "", limit: int = 100) -> list[JobPosting]:
        if not self.jobs_csv.exists():
            return []
        jobs: list[JobPosting] = []
        with self.jobs_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                job = JobPosting(
                    id=row.get("id") or f"job-{len(jobs)}",
                    title=row.get("title", ""),
                    company=row.get("company", ""),
                    description=row.get("description", ""),
                    skills=row.get("skills", ""),
                    min_experience=_to_float(row.get("min_experience")) or 0.0,
                    max_experience=_to_float(row.get("max_experience")),
                    location=row.get("location", ""),
                    remote=str(row.get("remote", "")).strip().lower() in ("1", "true", "yes"),
                    salary_min=_to_float(row.get("salary_min")),
                    salary_max=_to_float(row.get("salary_max")),
                    source=self.name,
                    raw_text=row.get("description", ""),
                )
                jobs.append(job)
        jobs = _text_filter(jobs, query, key=lambda j: f"{j.title} {j.description} {' '.join(j.skills)}")
        return jobs[:limit]


class SampleResumeSource(ResumeSource):
    name = "sample"

    def __init__(self, root: Path = SAMPLE_DIR) -> None:
        self.resume_dir = root / "resumes"
        self.meta_csv = root / "candidates.csv"

    def _load_meta(self) -> dict[str, dict[str, str]]:
        meta: dict[str, dict[str, str]] = {}
        if self.meta_csv.exists():
            with self.meta_csv.open(encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    key = (row.get("file") or "").strip()
                    if key:
                        meta[key] = row
        return meta

    def fetch_candidates(self, query: str = "", limit: int = 100) -> list[CandidateProfile]:
        if not self.resume_dir.exists():
            return []
        meta = self._load_meta()
        candidates: list[CandidateProfile] = []
        for path in sorted(self.resume_dir.glob("*.txt")):
            text = parse_resume_file(path)
            row = meta.get(path.name, {})
            years = _to_float(row.get("years_experience"))
            candidates.append(
                CandidateProfile(
                    id=row.get("id") or path.stem,
                    name=row.get("name", "") or path.stem.replace("_", " ").title(),
                    headline=row.get("headline", ""),
                    skills=row.get("skills") or extract_skills(text),
                    years_experience=years if years is not None else guess_years_experience(text),
                    location=row.get("location", ""),
                    desired_salary=_to_float(row.get("desired_salary")),
                    resume_text=text,
                    source=self.name,
                )
            )
        candidates = _text_filter(
            candidates, query, key=lambda c: f"{c.headline} {c.resume_text} {' '.join(c.skills)}"
        )
        return candidates[:limit]


def _text_filter(items, query, key):
    """Cheap case-insensitive substring filter used by the offline sample source."""
    q = (query or "").strip().lower()
    if not q:
        return items
    return [it for it in items if q in key(it).lower()]
