"""M4 vector-store tests — persistence, cache keying, and retrieval equivalence.

All against the TF-IDF backend (offline) with a tmp_path cache dir so nothing touches the
repo's data/ tree. The store is explicitly enabled per-instance; the global setting stays off
(see conftest.py).
"""

from __future__ import annotations

import numpy as np

from mindbridge.features.embeddings import TfidfEmbedder
from mindbridge.features.vector_store import VectorStore
from mindbridge.matching.retriever import SemanticRetriever

CORPUS = [
    "senior python backend engineer with django and aws",
    "android developer kotlin mobile apps",
    "data scientist machine learning pandas sklearn",
    "frontend developer react typescript css",
]
QUERY = "backend python engineer aws"


def _store(tmp_path, embedder=None) -> VectorStore:
    return VectorStore(embedder or TfidfEmbedder(), cache_dir=tmp_path, enabled=True)


def test_corpus_vectors_persist_and_reload(tmp_path):
    store = _store(tmp_path)
    matrix = store.corpus_vectors(CORPUS)
    assert matrix.shape[0] == len(CORPUS)
    # a cache entry landed on disk (sparse matrix + fitted vectorizer for tfidf)
    assert list(tmp_path.glob("*.sparse.npz")) and list(tmp_path.glob("*.vectorizer.pkl"))

    # a FRESH store (new embedder, cold memory) must serve the same matrix from disk
    reloaded = _store(tmp_path).corpus_vectors(CORPUS)
    assert (matrix != reloaded).nnz == 0  # sparse equality


def test_query_ranks_like_direct_encode(tmp_path):
    """The store-backed path must rank the corpus the same as the storeless joint encode."""
    with_store = SemanticRetriever(
        embedder=TfidfEmbedder(), vector_store=_store(tmp_path)
    ).rank(QUERY, CORPUS, top_k=len(CORPUS))
    without_store = SemanticRetriever(
        embedder=TfidfEmbedder(),
        vector_store=VectorStore(TfidfEmbedder(), cache_dir=tmp_path, enabled=False),
    ).rank(QUERY, CORPUS, top_k=len(CORPUS))

    assert [i for i, _ in with_store] == [i for i, _ in without_store]
    assert with_store[0][0] == 0  # the backend job wins for a backend query


def test_different_corpus_gets_different_key(tmp_path):
    store = _store(tmp_path)
    k1 = store._key(CORPUS)
    assert store._key(CORPUS[:-1]) != k1  # size change
    assert store._key(list(reversed(CORPUS))) != k1  # order change
    assert store._key([CORPUS[0] + "!", *CORPUS[1:]]) != k1  # content change
    assert store._key(CORPUS) == k1  # deterministic


def test_corrupt_cache_entry_is_rebuilt(tmp_path):
    store = _store(tmp_path)
    store.corpus_vectors(CORPUS)
    for p in tmp_path.iterdir():
        p.write_bytes(b"not a matrix")

    fresh = _store(tmp_path)
    matrix = fresh.corpus_vectors(CORPUS)  # must not raise
    assert matrix.shape[0] == len(CORPUS)


def test_query_vector_requires_corpus_for_tfidf(tmp_path):
    store = _store(tmp_path)
    try:
        store.query_vector(QUERY)
        assert False, "expected RuntimeError before corpus_vectors()"
    except RuntimeError:
        pass
    store.corpus_vectors(CORPUS)
    vec = store.query_vector(QUERY)
    assert isinstance(vec, np.ndarray) and vec.ndim == 1
    assert np.isclose(np.linalg.norm(vec), 1.0)  # L2-normalized


def test_disabled_store_touches_no_disk(tmp_path):
    retriever = SemanticRetriever(
        embedder=TfidfEmbedder(),
        vector_store=VectorStore(TfidfEmbedder(), cache_dir=tmp_path, enabled=False),
    )
    results = retriever.rank(QUERY, CORPUS, top_k=2)
    assert len(results) == 2
    assert not list(tmp_path.iterdir())
