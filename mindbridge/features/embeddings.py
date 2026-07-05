"""Pluggable text embedder.

Primary backend: sentence-transformers (semantic, high quality). If it can't be imported or the
model can't be downloaded (offline, no torch), we transparently fall back to a TF-IDF vectorizer
so the matching pipeline ALWAYS runs. Both backends expose the same `encode()` returning L2-
normalized vectors, so cosine similarity is just a dot product downstream.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from mindbridge.config import settings


class Embedder(ABC):
    backend: str = "base"

    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return an (n, dim) float32 array of L2-normalized row vectors."""


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (mat / norms).astype(np.float32)


class SentenceTransformerEmbedder(Embedder):
    backend = "sentence-transformers"

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # may raise ImportError

        self.model = SentenceTransformer(model_name)  # may hit the network on first use

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )
        return vecs.astype(np.float32)


class TfidfEmbedder(Embedder):
    """Offline fallback. Fits its vocabulary on the corpus passed to the FIRST encode() call
    (the matching engine encodes the full corpus up front), then reuses it for queries."""

    backend = "tfidf"

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._vectorizer = TfidfVectorizer(stop_words="english", max_features=4096, ngram_range=(1, 2))
        self._fitted = False

    def encode(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            mat = self._vectorizer.fit_transform(texts)
            self._fitted = True
        else:
            mat = self._vectorizer.transform(texts)
        return _l2_normalize(mat.toarray().astype(np.float32))


_CACHED: Embedder | None = None


def get_embedder(force_backend: str | None = None) -> Embedder:
    """Return a process-wide singleton embedder.

    force_backend: "sentence-transformers" | "tfidf" | None (auto). Auto tries the transformer
    model and falls back to TF-IDF on any failure.
    """
    global _CACHED
    if _CACHED is not None and force_backend is None:
        return _CACHED

    if force_backend == "tfidf":
        _CACHED = TfidfEmbedder()
        return _CACHED

    if force_backend == "sentence-transformers":
        _CACHED = SentenceTransformerEmbedder(settings.embed_model)
        return _CACHED

    # auto
    try:
        _CACHED = SentenceTransformerEmbedder(settings.embed_model)
    except Exception:
        # ImportError (no torch) or network/model-load failure -> stay usable offline.
        _CACHED = TfidfEmbedder()
    return _CACHED
