"""Feature extraction: semantic embeddings and structured (skill/experience/location/salary) signals."""

from mindbridge.features.embeddings import Embedder, get_embedder
from mindbridge.features.structured import StructuredFeatures, compute_structured_features

__all__ = ["Embedder", "get_embedder", "StructuredFeatures", "compute_structured_features"]
