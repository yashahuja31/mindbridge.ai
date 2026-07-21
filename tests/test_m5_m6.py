"""Tests for Milestone 5 (Outcome Feedback & Reranker Training) and Milestone 6 (ANN Index)."""

from __future__ import annotations

import numpy as np
import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mindbridge.matching.ann_index import ANNIndex
from mindbridge.matching.retriever import SemanticRetriever
from mindbridge.schemas import MatchResult
from mindbridge.training.make_labels import build_training_table_from_history
from mindbridge.training.train_reranker import train_from_history
from mindbridge.web import models, services
from mindbridge.web.db import Base
from mindbridge.web.models import MatchHistory, User


@pytest.fixture
def db_session(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test_m5.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_m5_feedback_and_outcome_training(db_session):
    # Create test user
    user = User(email="test_m5@example.com", hashed_password="hashed_password", role="hiree")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create dummy match results
    res1 = MatchResult(
        subject_id="cand-1",
        matched_id="job-101",
        matched_label="Senior Backend Engineer",
        score=0.85,
        semantic_score=0.80,
        feature_breakdown={"skill_coverage": 0.9, "experience_match": 0.8},
    )
    res2 = MatchResult(
        subject_id="cand-1",
        matched_id="job-102",
        matched_label="Frontend Developer",
        score=0.60,
        semantic_score=0.55,
        feature_breakdown={"skill_coverage": 0.5, "experience_match": 0.6},
    )

    # Save history
    record = services.save_history(db_session, user, "jobs", "Test match", [res1, res2])
    assert record.id is not None

    # Record outcome feedback
    updated = services.record_feedback(
        db_session, user, record.id, item_id="job-101", outcome="hired"
    )
    assert updated.outcome_label == 1.0

    # Build dataset from history
    table = build_training_table_from_history(db_session)
    assert len(table) >= 1
    assert "label" in table.columns
    assert "semantic_score" in table.columns
    assert table.iloc[0]["label"] == 1.0

    # Train model on history
    metrics = train_from_history(db=db_session, save=False)
    assert metrics["n_samples"] >= 1.0
    assert "train_mae" in metrics


def test_m6_ann_index_direct():
    np.random.seed(42)
    vecs = np.random.randn(50, 16).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / norms

    ann = ANNIndex(backend="sklearn").fit(vecs)
    assert ann.num_vectors == 50
    assert ann.dim == 16

    results = ann.query(vecs[0], top_k=5)
    assert len(results) == 5
    top_idx, top_sim = results[0]
    assert top_idx == 0
    assert top_sim >= 0.99  # exact match query against itself


def test_m6_semantic_retriever_ann(monkeypatch):
    texts = [
        "Senior Python Engineer with Django AWS PostgreSQL",
        "Frontend React TypeScript Developer",
        "Machine Learning Engineer PyTorch NLP",
        "DevOps Cloud Kubernetes Terraform AWS",
        "Data Scientist Pandas Scikit-Learn Statistics",
        "iOS Swift Mobile App Developer",
    ]

    retriever = SemanticRetriever(use_ann=True)
    retriever.ann_threshold = 3  # force ANN threshold low for test

    ranked = retriever.rank("Python Django Backend", texts, top_k=3)
    assert len(ranked) == 3
    top_idx, top_score = ranked[0]
    assert top_idx == 0  # Python Engineer matched top
