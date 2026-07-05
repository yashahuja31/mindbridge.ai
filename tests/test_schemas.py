from mindbridge.schemas import CandidateProfile, JobPosting, MatchResult


def test_skills_coerced_from_string():
    job = JobPosting(id="j1", title="Dev", skills="Python; Django, AWS|Docker")
    assert job.skills == ["python", "django", "aws", "docker"]


def test_skills_deduped_and_lowercased():
    cand = CandidateProfile(id="c1", skills=["Python", "python", "SQL"])
    assert cand.skills == ["python", "sql"]


def test_matchable_text_includes_key_fields():
    job = JobPosting(id="j1", title="Backend Engineer", company="Acme", skills=["python"])
    text = job.matchable_text()
    assert "Backend Engineer" in text and "Acme" in text and "python" in text


def test_matchresult_scores_clamped_to_unit_interval():
    r = MatchResult(subject_id="a", matched_id="b", score=1.5, semantic_score=-0.2)
    assert r.score == 1.0
    assert r.semantic_score == 0.0
