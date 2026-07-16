"""Shared test fixtures.

Tests force the TF-IDF embedder so the suite runs fast and fully offline — no torch download,
no network. The transformer backend is exercised separately/manually, not in unit tests.

The persistent vector store (M4) is disabled globally here so tests never write cache files
into the repo's data/ tree; `tests/test_vector_store.py` re-enables it explicitly against a
tmp_path cache directory.
"""

import pytest

from mindbridge.config import settings
from mindbridge.features.embeddings import TfidfEmbedder
from mindbridge.matching.engine import MatchEngine
from mindbridge.matching.reranker import HeuristicReranker
from mindbridge.matching.retriever import SemanticRetriever

settings.vector_store = False  # keep tests hermetic (no on-disk vector cache)


@pytest.fixture
def tfidf_engine() -> MatchEngine:
    retriever = SemanticRetriever(embedder=TfidfEmbedder())
    return MatchEngine(retriever=retriever, reranker=HeuristicReranker())
