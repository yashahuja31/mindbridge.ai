from mindbridge.features.structured import (
    FEATURE_NAMES,
    compute_structured_features,
)
from mindbridge.ingestion.registry import load_candidates, load_jobs
from mindbridge.schemas import CandidateProfile, JobPosting


def _candidate(cands, cid):
    return next(c for c in cands if c.id == cid)


def _job(jobs, jid):
    return next(j for j in jobs if j.id == jid)


def test_structured_features_reward_skill_overlap():
    job = JobPosting(id="j", title="Backend", skills=["python", "django", "aws"])
    strong = CandidateProfile(id="s", skills=["python", "django", "aws"], years_experience=6)
    weak = CandidateProfile(id="w", skills=["kotlin", "android"], years_experience=6)
    assert compute_structured_features(strong, job).skill_coverage == 1.0
    assert compute_structured_features(weak, job).skill_coverage == 0.0


def test_role_match_populated_from_taxonomy():
    # headline vs title drive role_match; exact canonical match -> 1.0
    job = JobPosting(id="j", title="Backend Engineer", skills=["python"])
    cand = CandidateProfile(id="c", headline="Senior Backend Developer", skills=["python"])
    feats = compute_structured_features(cand, job)
    assert feats.role_match == 1.0

    # unrelated recognized role -> neutral 0.5 (not zero)
    pm = CandidateProfile(id="c2", headline="Product Manager", skills=["python"])
    assert compute_structured_features(pm, job).role_match == 0.5


def test_feature_vector_layout_matches_names():
    job = JobPosting(id="j", title="Backend", skills=["python"])
    cand = CandidateProfile(id="c", headline="Backend Developer", skills=["python"])
    feats = compute_structured_features(cand, job)
    # role_match is the 6th feature, appended after the original five
    assert FEATURE_NAMES[-1] == "role_match"
    assert len(feats.vector()) == len(FEATURE_NAMES) == 6
    assert set(feats.as_dict()) == set(FEATURE_NAMES)


def test_engine_returns_ranked_results(tfidf_engine):
    jobs = load_jobs(sources=["sample"])
    cands = load_candidates(sources=["sample"])
    ravi = _candidate(cands, "c-001")  # backend engineer

    results = tfidf_engine.match_jobs_for_candidate(ravi, jobs, k=5)
    assert len(results) == 5
    # sorted descending by score, all in [0,1], all explained
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert all(r.reasons for r in results)


def test_backend_resume_matches_backend_job_over_android(tfidf_engine):
    """The core sanity check: a clearly-fitting job outranks a clearly-mismatched one."""
    jobs = load_jobs(sources=["sample"])
    cands = load_candidates(sources=["sample"])
    ravi = _candidate(cands, "c-001")

    results = tfidf_engine.match_jobs_for_candidate(ravi, jobs, k=len(jobs))
    by_job = {r.matched_id: r.score for r in results}
    assert by_job["j-001"] > by_job["j-009"]  # Senior Backend Engineer > Android Developer


def test_reverse_direction_candidates_for_job(tfidf_engine):
    jobs = load_jobs(sources=["sample"])
    cands = load_candidates(sources=["sample"])
    backend_job = _job(jobs, "j-001")

    results = tfidf_engine.match_candidates_for_job(backend_job, cands, k=len(cands))
    by_cand = {r.matched_id: r.score for r in results}
    # backend engineer should beat the android developer for a backend role
    assert by_cand["c-001"] > by_cand["c-008"]
