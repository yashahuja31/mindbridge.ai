import pytest

from mindbridge.ingestion.registry import load_candidates, load_jobs
from mindbridge.ingestion.scraper_source import ScraperDisabledError, ScraperJobSource


def test_sample_jobs_load():
    jobs = load_jobs(sources=["sample"])
    assert len(jobs) >= 10
    ids = {j.id for j in jobs}
    assert "j-001" in ids
    j1 = next(j for j in jobs if j.id == "j-001")
    assert "python" in j1.skills
    assert j1.source == "sample"


def test_sample_candidates_load_with_metadata():
    cands = load_candidates(sources=["sample"])
    assert len(cands) >= 8
    ravi = next(c for c in cands if c.id == "c-001")
    assert ravi.name == "Ravi Patel"
    assert ravi.years_experience == 7
    assert "python" in ravi.skills  # extracted from resume text


def test_job_query_filter():
    all_jobs = load_jobs(sources=["sample"])
    android = load_jobs(query="android", sources=["sample"])
    assert 0 < len(android) < len(all_jobs)


def test_scraper_disabled_by_default():
    with pytest.raises(ScraperDisabledError):
        ScraperJobSource().fetch_jobs()


def test_registry_skips_failing_source():
    # scraper raises, but the registry must not let that break the run.
    jobs = load_jobs(sources=["sample", "scraper"])
    assert len(jobs) >= 10
