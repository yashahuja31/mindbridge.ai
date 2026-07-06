"""Train the stage-2 reranker (XGBoost) and save the artifact the engine auto-loads.

Run as a script:
    python -m mindbridge.training.train_reranker

It pulls sample candidates + jobs, builds the training table (weak labels at cold start; real
outcome labels once you have them), fits an XGBoost regressor, reports train/val error, and writes
`models/reranker.json`. On the next run, `get_reranker()` picks up that file and the engine uses
the learned model instead of the heuristic — no other code changes.
"""

from __future__ import annotations

from mindbridge.config import MODELS_DIR
from mindbridge.features.structured import FEATURE_NAMES
from mindbridge.ingestion.registry import load_candidates, load_jobs
from mindbridge.training.make_labels import build_training_table

MODEL_OUT = MODELS_DIR / "reranker.json"
FEATURE_COLUMNS = [*FEATURE_NAMES, "semantic_score"]


def _fit_and_report(table, save: bool) -> dict[str, float]:
    """Shared training core: fit XGBoost on a prebuilt table, report MAE, optionally save."""
    import xgboost as xgb
    from sklearn.metrics import mean_absolute_error
    from sklearn.model_selection import train_test_split

    X = table[FEATURE_COLUMNS].to_numpy(dtype="float32")
    y = table["label"].to_numpy(dtype="float32")

    # With tiny sample data, keep a small holdout just to report a number.
    if len(table) >= 10:
        X_tr, X_val, y_tr, y_val = train_test_split(X, y, test_size=0.2, random_state=42)
    else:
        X_tr, X_val, y_tr, y_val = X, X, y, y

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        objective="reg:squarederror",
    )
    model.fit(X_tr, y_tr)

    metrics = {
        "n_samples": float(len(table)),
        "train_mae": float(mean_absolute_error(y_tr, model.predict(X_tr))),
        "val_mae": float(mean_absolute_error(y_val, model.predict(X_val))),
    }

    if save:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        model.save_model(str(MODEL_OUT))
        metrics["saved_to"] = str(MODEL_OUT)  # type: ignore[assignment]

    return metrics


def train(save: bool = True) -> dict[str, float]:
    candidates = load_candidates(sources=["sample"])
    jobs = load_jobs(sources=["sample"])
    if not candidates or not jobs:
        raise RuntimeError(
            "No sample data found. Ensure data/sample/jobs.csv and data/sample/resumes/*.txt exist."
        )

    table = build_training_table(candidates, jobs)
    return _fit_and_report(table, save)


def train_on_corpus(
    save: bool = True, limit: int | None = None, pairs_per_candidate: int = 20
) -> dict[str, float]:
    """Train on the 10k demo corpus instead of the tiny sample set.

    All-pairs over 10k x 10k is ~100M rows — far too many. We instead pair each candidate with a
    bounded random-but-deterministic slice of jobs (`pairs_per_candidate`), keeping the table big
    enough for honest metrics while staying tractable. Labels are still the heuristic's own score
    (proxy labels; see make_labels), so this distills the *rebalanced* demo weights, not real
    outcomes — the M5 payoff still needs true hire/satisfaction data.
    """
    from mindbridge.ingestion.corpus_build import load_cached_candidates, load_cached_jobs

    candidates = load_cached_candidates(limit=limit)
    jobs = load_cached_jobs(limit=limit)
    if not candidates or not jobs:
        raise RuntimeError(
            "Demo corpus is empty. Run `python -m mindbridge.cli build-corpus` first."
        )

    # Deterministic bounded pairing: candidate i sees a contiguous window of jobs starting at a
    # stride-offset, so every candidate contributes rows without materializing the full cross join.
    n_jobs = len(jobs)
    window = min(pairs_per_candidate, n_jobs)
    subtables = []
    for i, cand in enumerate(candidates):
        start = (i * window) % n_jobs
        picked = [jobs[(start + j) % n_jobs] for j in range(window)]
        subtables.append(build_training_table([cand], picked))

    import pandas as pd

    table = pd.concat(subtables, ignore_index=True)
    return _fit_and_report(table, save)


if __name__ == "__main__":
    import json

    print(json.dumps(train(), indent=2, default=str))
