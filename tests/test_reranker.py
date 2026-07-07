"""Reranker artifact-compatibility guard.

A model trained on a stale feature layout (e.g. before a feature was appended to FEATURE_NAMES)
must be rejected at *load* so `get_reranker()` can fall back to the transparent heuristic —
instead of loading fine and then crashing at predict time on every score() call. These tests pin
that behavior, which the web layer depends on for graceful degradation.
"""

from __future__ import annotations

import numpy as np
import pytest

from mindbridge.matching import reranker as rr_mod
from mindbridge.matching.reranker import (
    HeuristicReranker,
    ModelReranker,
    get_reranker,
    model_feature_names,
)
from mindbridge.schemas import CandidateProfile, JobPosting


def _make_xgb_model(n_features: int, path) -> None:
    xgb = pytest.importorskip("xgboost")
    rng = np.random.default_rng(0)
    X = rng.random((40, n_features)).astype("float32")
    y = rng.random(40).astype("float32")
    model = xgb.XGBRegressor(n_estimators=10, max_depth=2)
    model.fit(X, y)
    model.save_model(str(path))


def test_incompatible_artifact_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    _make_xgb_model(len(model_feature_names()) - 1, bad)  # one feature short of the contract
    with pytest.raises(ValueError):
        ModelReranker(bad)


def test_compatible_artifact_loads_and_scores(tmp_path):
    good = tmp_path / "good.json"
    _make_xgb_model(len(model_feature_names()), good)
    rr = ModelReranker(good)
    job = JobPosting(id="j", title="Backend Engineer", skills=["python", "aws"])
    cand = CandidateProfile(
        id="c", headline="Backend Developer", skills=["python"], years_experience=5
    )
    res = rr.score(cand, job, 0.7)
    assert 0.0 <= res.score <= 1.0
    assert res.reasons  # explanations are always produced


def test_get_reranker_falls_back_to_heuristic_on_incompatible_artifact(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    _make_xgb_model(len(model_feature_names()) - 1, bad)
    monkeypatch.setattr(rr_mod, "MODEL_PATH", bad)
    assert isinstance(get_reranker(), HeuristicReranker)
