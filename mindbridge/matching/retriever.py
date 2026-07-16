"""Stage 1 — semantic retrieval.

Embed a query and a corpus, rank the corpus by cosine similarity to the query, return the top-K
(index, similarity) pairs. Because the embedder returns L2-normalized vectors, cosine similarity
is a plain dot product. At sample scale a dense numpy matmul is more than fast enough — no FAISS.

M4: corpus embeddings come from the persistent `VectorStore` when enabled, so repeated matches
against the same corpus (the common case for a running server — every request re-ranks the same
10k demo jobs) skip re-encoding entirely. Any store failure falls back to the original joint
encode, so retrieval never breaks on a cache problem.
"""

from __future__ import annotations

import numpy as np

from mindbridge.features.embeddings import Embedder, get_embedder


class SemanticRetriever:
    def __init__(self, embedder: Embedder | None = None, vector_store=None) -> None:
        self.embedder = embedder or get_embedder()
        if vector_store is None:
            from mindbridge.features.vector_store import VectorStore

            vector_store = VectorStore(self.embedder)
        self.vector_store = vector_store

    def rank(self, query_text: str, corpus_texts: list[str], top_k: int) -> list[tuple[int, float]]:
        """Return up to `top_k` (corpus_index, similarity in [0,1]) pairs, highest first."""
        if not corpus_texts:
            return []

        sims = self._similarities(query_text, corpus_texts)
        # Map cosine [-1,1] -> [0,1] for a consistent, explainable score.
        sims = (sims + 1.0) / 2.0

        k = min(top_k, len(corpus_texts))
        top_idx = np.argsort(-sims)[:k]
        return [(int(i), float(sims[i])) for i in top_idx]

    def _similarities(self, query_text: str, corpus_texts: list[str]) -> np.ndarray:
        """Cosine similarity of the query against every corpus row (rows are L2-normalized)."""
        if self.vector_store.enabled:
            try:
                matrix = self.vector_store.corpus_vectors(corpus_texts)
                query_vec = self.vector_store.query_vector(query_text)
                return np.asarray(matrix @ query_vec).ravel()
            except Exception:
                pass  # any cache trouble -> the always-works path below

        # Encode corpus + query together so the TF-IDF fallback fits its vocabulary on everything.
        matrix = self.embedder.encode(corpus_texts + [query_text])
        corpus_vecs, query_vec = matrix[:-1], matrix[-1]
        return corpus_vecs @ query_vec
