"""Tests for the demo-corpus cache builder and the 'demo' ingestion source.

These are isolated from the real 10k zips and the real data/processed cache: we build tiny
throwaway zips in a tmp dir and repoint the corpus_build module's path constants at them, so the
suite stays fast, offline, and never touches committed/gitignored artifacts.
"""

import zipfile

import pytest

from mindbridge.ingestion import corpus_build

RESUME_MD = """# Alex Doe

**Target Role:** Backend Developer

Location: Remote

## Skills
Python, Django, PostgreSQL
"""

JOB_MD = """# Backend Developer

Company: Acme

## About the Role
Build APIs.

## Required Skills
- Python
- Django

Reference ID: JD-TEST-1
"""


def _make_zip(path, prefix, body, n):
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(1, n + 1):
            zf.writestr(f"{prefix}_{i:05d}.md", body)


@pytest.fixture
def tmp_corpus(tmp_path, monkeypatch):
    """Repoint corpus_build at tiny tmp zips + a tmp processed dir."""
    jobs_zip = tmp_path / "jobs.zip"
    resumes_zip = tmp_path / "resumes.zip"
    _make_zip(jobs_zip, "job_description", JOB_MD, 3)
    _make_zip(resumes_zip, "resume", RESUME_MD, 3)

    processed = tmp_path / "processed"
    monkeypatch.setattr(corpus_build, "JOBS_ZIP", jobs_zip)
    monkeypatch.setattr(corpus_build, "RESUMES_ZIP", resumes_zip)
    monkeypatch.setattr(corpus_build, "PROCESSED_DIR", processed)
    monkeypatch.setattr(corpus_build, "JOBS_PARQUET", processed / "jobs.parquet")
    monkeypatch.setattr(corpus_build, "JOBS_JSONL", processed / "jobs.jsonl")
    monkeypatch.setattr(corpus_build, "CANDS_PARQUET", processed / "candidates.parquet")
    monkeypatch.setattr(corpus_build, "CANDS_JSONL", processed / "candidates.jsonl")
    # corpus_limit=None so we read everything we wrote
    monkeypatch.setattr(corpus_build.settings, "corpus_limit", None, raising=False)
    return processed


def test_build_corpus_creates_cache_and_counts(tmp_corpus):
    stats = corpus_build.build_corpus(force=True)
    assert stats == {"jobs": 3, "candidates": 3, "rebuilt": 1}
    assert corpus_build.corpus_cached()


def test_build_corpus_is_idempotent_without_force(tmp_corpus):
    corpus_build.build_corpus(force=True)
    again = corpus_build.build_corpus(force=False)
    assert again["rebuilt"] == 0
    assert again["jobs"] == 3


def test_cache_round_trips_domain_objects(tmp_corpus):
    corpus_build.build_corpus(force=True)
    jobs = corpus_build.load_cached_jobs()
    cands = corpus_build.load_cached_candidates()

    assert len(jobs) == 3 and len(cands) == 3
    j = jobs[0]
    assert j.id == "JD-TEST-1"  # parsed Reference ID survived the cache round-trip
    assert "python" in j.skills
    assert j.source == "demo"

    c = cands[0]
    assert c.headline == "Backend Developer"
    assert "django" in c.skills


def test_limit_caps_docs_per_side(tmp_corpus):
    stats = corpus_build.build_corpus(force=True, limit=2)
    assert stats["jobs"] == 2 and stats["candidates"] == 2


def test_load_builds_cache_on_demand(tmp_corpus):
    # no explicit build() call: loader must build the cache itself
    assert not corpus_build.corpus_cached()
    cands = corpus_build.load_cached_candidates()
    assert len(cands) == 3
    assert corpus_build.corpus_cached()
