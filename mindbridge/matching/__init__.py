"""The two-stage hybrid matching pipeline: retrieve (embeddings) → rerank (features) → results."""

from mindbridge.matching.engine import MatchEngine

__all__ = ["MatchEngine"]
