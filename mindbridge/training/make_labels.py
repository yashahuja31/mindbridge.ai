"""Generate a training table for the reranker.

The real signal we eventually want is *outcomes*: was a candidate hired, and did they stay and
thrive? That data doesn't exist at cold start. So this module builds a bootstrap table by pairing
every candidate with every job, computing the feature vector, and using a weak label:

    weak_label = the heuristic reranker's own blended score

Training on that alone just distills the heuristic — useful as a smoke test and a scaffold, not a
quality gain. The moment you have real labels (a `hired`/`satisfaction` column from the product),
feed them in via `label_column` and you get a genuinely learned model with no other code change.

Output: a pandas DataFrame with FEATURE_NAMES + "semantic_score" + "label".
"""

from __future__ import annotations

import pandas as pd

from mindbridge.features.embeddings import get_embedder
from mindbridge.features.structured import FEATURE_NAMES, compute_structured_features
from mindbridge.matching.reranker import HeuristicReranker
from mindbridge.matching.retriever import SemanticRetriever
from mindbridge.schemas import CandidateProfile, JobPosting


def build_training_table(
    candidates: list[CandidateProfile], jobs: list[JobPosting]
) -> pd.DataFrame:
    retriever = SemanticRetriever(embedder=get_embedder())
    heuristic = HeuristicReranker()

    # Precompute semantic scores candidate-by-candidate against the full job corpus.
    job_texts = [j.matchable_text() for j in jobs]
    rows: list[dict[str, float]] = []
    for cand in candidates:
        ranked = retriever.rank(cand.matchable_text(), job_texts, top_k=len(jobs))
        sem_by_idx = {idx: sem for idx, sem in ranked}
        for j_idx, job in enumerate(jobs):
            sem = sem_by_idx.get(j_idx, 0.0)
            feats = compute_structured_features(cand, job)
            rr = heuristic.score(cand, job, sem)
            row = feats.as_dict()
            row["semantic_score"] = float(sem)
            row["label"] = float(rr.score)  # weak label; replace with real outcomes when available
            rows.append(row)

    columns = [*FEATURE_NAMES, "semantic_score", "label"]
    return pd.DataFrame(rows, columns=columns)
