"""M6: ANN-backed approximate nearest neighbor vector search index.

Pluggable vector index supporting:
  - HNSW (via `hnswlib` if installed)
  - FAISS (via `faiss` if installed)
  - Scikit-Learn `NearestNeighbors` (zero-config fallback built into core dependencies)

Sub-linear stage-1 search seam for scaling stage-1 retrieval as the corpus grows.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger("mindbridge.matching.ann")


class ANNIndex:
    """Approximate Nearest Neighbor index wrapping HNSWlib, FAISS, or Scikit-Learn."""

    def __init__(self, backend: str = "auto") -> None:
        self.backend_requested = backend
        self.backend_active = "sklearn"
        self._index: Any = None
        self._vectors: Optional[np.ndarray] = None
        self.dim = 0
        self.num_vectors = 0

    def fit(self, matrix: Any) -> "ANNIndex":
        """Build the vector index over an (N, D) corpus matrix (dense or sparse)."""
        if hasattr(matrix, "toarray"):
            matrix = matrix.toarray()

        arr = np.asarray(matrix, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)

        self.num_vectors, self.dim = arr.shape
        if self.num_vectors == 0:
            return self

        # Normalize L2 so Euclidean / Cosine correspond
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        arr_norm = arr / norms
        self._vectors = arr_norm

        backend_to_try = self.backend_requested.lower()

        # Try HNSWlib
        if backend_to_try in ("auto", "hnsw", "hnswlib"):
            try:
                import hnswlib

                idx = hnswlib.Index(space="cosine", dim=self.dim)
                idx.init_index(max_elements=self.num_vectors, ef_construction=100, M=16)
                idx.add_items(arr_norm, np.arange(self.num_vectors))
                idx.set_ef(max(50, self.num_vectors // 10))
                self._index = idx
                self.backend_active = "hnsw"
                return self
            except Exception:
                if backend_to_try in ("hnsw", "hnswlib"):
                    logger.warning("hnswlib requested but unavailable; falling back to sklearn")

        # Try FAISS
        if backend_to_try in ("auto", "faiss"):
            try:
                import faiss

                idx = faiss.IndexFlatIP(self.dim)  # Inner product on L2-normalized = cosine
                idx.add(arr_norm)
                self._index = idx
                self.backend_active = "faiss"
                return self
            except Exception:
                if backend_to_try == "faiss":
                    logger.warning("faiss requested but unavailable; falling back to sklearn")

        # Zero-config Scikit-Learn fallback
        from sklearn.neighbors import NearestNeighbors

        nn = NearestNeighbors(
            n_neighbors=min(100, self.num_vectors),
            algorithm="auto",
            metric="cosine",
        )
        nn.fit(arr_norm)
        self._index = nn
        self.backend_active = "sklearn"
        return self

    def query(self, query_vec: Any, top_k: int = 10) -> list[tuple[int, float]]:
        """Search top_k nearest neighbors for a single query vector.

        Returns list of (index, similarity_in_[0,1]) sorted by highest similarity.
        """
        if self.num_vectors == 0 or self._index is None:
            return []

        q = np.asarray(query_vec, dtype=np.float32).ravel()
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm
        q = q.reshape(1, -1)

        k = min(top_k, self.num_vectors)

        if self.backend_active == "hnsw":
            labels, distances = self._index.knn_query(q, k=k)
            # hnswlib cosine space returns cosine distance = 1 - cosine_sim
            indices = labels[0]
            sims = 1.0 - distances[0]
        elif self.backend_active == "faiss":
            distances, labels = self._index.search(q, k)
            indices = labels[0]
            sims = distances[0]
        else:
            # sklearn NearestNeighbors
            distances, indices = self._index.kneighbors(q, n_neighbors=k)
            indices = indices[0]
            # sklearn cosine distance = 1 - cosine_sim
            sims = 1.0 - distances[0]

        # Map cosine similarity [-1, 1] -> [0, 1]
        sims_clamped = (np.clip(sims, -1.0, 1.0) + 1.0) / 2.0

        results = []
        for idx, score in zip(indices, sims_clamped):
            if idx >= 0:
                results.append((int(idx), float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results
