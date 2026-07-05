"""Shared test fixtures.

Tests force the TF-IDF embedder so the suite runs fast and fully offline — no torch download,
no network. The transformer backend is exercised separately/manually, not in unit tests.
"""

import pytest

from mindbridge.features.embeddings import TfidfEmbedder
from mindbridge.matching.engine import MatchEngine
from mindbridge.matching.reranker import HeuristicReranker
from mindbridge.matching.retriever import SemanticRetriever


@pytest.fixture
def tfidf_engine() -> MatchEngine:
    retriever = SemanticRetriever(embedder=TfidfEmbedder())
    return MatchEngine(retriever=retriever, reranker=HeuristicReranker())
