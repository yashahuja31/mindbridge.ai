"""Stage 1 — semantic retrieval.

Embed a query and a corpus, rank the corpus by cosine similarity to the query, return the top-K
(index, similarity) pairs. Because the embedder returns L2-normalized vectors, cosine similarity
is a plain dot product. At sample scale a dense numpy matmul is more than fast enough — no FAISS.
"""

from __future__ import annotations

import numpy as np

from mindbridge.features.embeddings import Embedder, get_embedder


class SemanticRetriever:
    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or get_embedder()

    def rank(self, query_text: str, corpus_texts: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return up to `top_k` (corpus_index, similarity in [0,1]) pairs, highest first."""
        if not corpus_texts:
            return []
        # Encode corpus + query together so the TF-IDF fallback fits its vocabulary on everything.
        matrix = self.embedder.encode(corpus_texts + [query_text])
        corpus_vecs, query_vec = matrix[:-1], matrix[-1]

        sims = corpus_vecs @ query_vec  # cosine, since rows are normalized
        # Map cosine [-1,1] -> [0,1] for a consistent, explainable score.
        sims = (sims + 1.0) / 2.0

        k = min(top_k, len(corpus_texts))
        top_idx = np.argsort(-sims)[:k]
        return [(int(i), float(sims[i])) for i in top_idx]
