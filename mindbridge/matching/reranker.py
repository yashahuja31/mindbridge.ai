"""Stage 2 — reranking.

Given a candidate/job pair plus the stage-1 semantic score, produce a final blended score in
[0, 1] AND the human-readable reasons that make the match explainable.

Two modes, same interface:
  * HeuristicReranker — transparent weighted blend of semantic score + structured features.
    Needs no training data, so it's the default and the cold-start engine.
  * ModelReranker — loads a trained XGBoost model (models/reranker.json) and predicts the score
    from the feature vector. Used automatically when the artifact exists.

`get_reranker()` returns the model-backed one if an artifact is present, else the heuristic.
"""

from __future__ import annotations

from pathlib import Path

from mindbridge.config import MODELS_DIR, settings
from mindbridge.features.structured import (
    FEATURE_NAMES,
    StructuredFeatures,
    compute_structured_features,
)
from mindbridge.schemas import CandidateProfile, JobPosting

MODEL_PATH = MODELS_DIR / "reranker.json"


class RerankResult:
    """Small carrier for a reranked pair."""

    def __init__(self, score: float, reasons: list[str], breakdown: dict[str, float]) -> None:
        self.score = max(0.0, min(1.0, score))
        self.reasons = reasons
        self.breakdown = breakdown


def _build_reasons(sem: float, feats: StructuredFeatures) -> list[str]:
    """Turn scores into plain-English 'why this match' bullets, best signals first."""
    reasons: list[str] = []
    if feats.role_match >= 0.99:
        reasons.append("Role matches the target exactly")
    elif feats.role_match >= 0.6:
        reasons.append("Role is closely related to the target")
    elif feats.role_match <= 0.45:
        reasons.append("Role differs from the target")
    if feats.matched_skills:
        shown = ", ".join(feats.matched_skills[:6])
        reasons.append(f"Shares {len(feats.matched_skills)} key skill(s): {shown}")
    if feats.experience_match >= 0.8:
        reasons.append("Experience level fits the role's range")
    elif feats.experience_match <= 0.4:
        reasons.append("Experience is outside the role's expected range")
    if feats.location_match >= 0.9:
        reasons.append("Location/remote preferences align")
    if feats.salary_fit >= 0.9:
        reasons.append("Salary expectations fit the posted band")
    elif feats.salary_fit <= 0.3:
        reasons.append("Salary expectations may be above the posted band")
    if sem >= 0.7:
        reasons.append("Strong overall semantic similarity between profile and role")
    if feats.missing_skills:
        reasons.append("Gaps: " + ", ".join(feats.missing_skills[:5]))
    return reasons


class HeuristicReranker:
    backend = "heuristic"

    def score(
        self, cand: CandidateProfile, job: JobPosting, semantic_score: float
    ) -> RerankResult:
        feats = compute_structured_features(cand, job)
        w = settings
        blended = (
            w.w_semantic * semantic_score
            + w.w_skills * (0.5 * feats.skill_coverage + 0.5 * feats.skill_overlap)
            + w.w_role * feats.role_match
            + w.w_experience * feats.experience_match
            + w.w_location * feats.location_match
            + w.w_salary * feats.salary_fit
        )
        total_w = (
            w.w_semantic + w.w_skills + w.w_role + w.w_experience + w.w_location + w.w_salary
        )
        blended = blended / total_w if total_w else blended

        breakdown = feats.as_dict()
        breakdown["semantic"] = round(float(semantic_score), 4)
        return RerankResult(blended, _build_reasons(semantic_score, feats), breakdown)


class ModelReranker:
    """XGBoost-backed reranker. Falls back to raising on load failure; `get_reranker` handles that."""

    backend = "model"

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        import xgboost as xgb  # imported here so the heuristic path needs no xgboost

        self.model = xgb.XGBRegressor()
        self.model.load_model(str(model_path))
        # Guard the feature-vector contract: a model trained on a different feature layout (e.g.
        # before a feature was added to FEATURE_NAMES) would only blow up later at predict time,
        # crashing live scoring. Validate up front so `get_reranker` can fall back to the heuristic
        # — that's the documented "incompatible artifact -> heuristic" behavior.
        expected = len(model_feature_names())
        actual = self.model.get_booster().num_features()
        if actual != expected:
            raise ValueError(
                f"Reranker artifact expects {actual} features but the current layout needs "
                f"{expected}. Retrain with `python -m mindbridge.cli train`."
            )

    def score(
        self, cand: CandidateProfile, job: JobPosting, semantic_score: float
    ) -> RerankResult:
        import numpy as np

        feats = compute_structured_features(cand, job)
        # Model consumes [structured features..., semantic_score] in a fixed order.
        vector = feats.vector() + [float(semantic_score)]
        pred = float(self.model.predict(np.array([vector], dtype="float32"))[0])
        breakdown = feats.as_dict()
        breakdown["semantic"] = round(float(semantic_score), 4)
        return RerankResult(pred, _build_reasons(semantic_score, feats), breakdown)


def model_feature_names() -> list[str]:
    """Feature-vector layout the trained model expects (kept in one place)."""
    return [*FEATURE_NAMES, "semantic_score"]


def get_reranker():
    """Prefer the trained model if its artifact exists; otherwise use the heuristic."""
    if MODEL_PATH.exists():
        try:
            return ModelReranker(MODEL_PATH)
        except Exception:
            # Corrupt/incompatible artifact or missing xgboost -> stay functional.
            return HeuristicReranker()
    return HeuristicReranker()
