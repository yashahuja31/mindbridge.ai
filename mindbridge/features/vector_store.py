"""Persistent stage-1 vector store (M4).

Re-embedding the corpus on every process start is the M4 scaling bottleneck: the demo corpus
alone is 20k documents, and the transformer backend takes minutes to encode it. This module
caches corpus embeddings on disk keyed by (embedder backend, corpus fingerprint) so a warm
start loads vectors instead of recomputing them.

Design notes:
- The key is a SHA-256 over the ordered corpus texts plus the backend (and model name for the
  transformer), so any change to the corpus — content, order, size — or the embedder produces
  a different key. A stale cache can never be served; it just stops being hit.
- TF-IDF is corpus-stateful: query vectors must come from the SAME fitted vocabulary as the
  cached corpus matrix, so the fitted vectorizer is persisted next to the vectors. The store
  fits on the corpus ONLY and transforms queries against it (unlike the joint corpus+query fit
  of the storeless path — scores shift a hair, ordering doesn't).
- Transformer embeddings are corpus-stateless: only the matrix is cached, queries encode live.
- Graceful degradation, as everywhere in this codebase: any cache read/write failure falls
  back to a straight re-encode. The store never breaks a match run.
- TF-IDF matrices are kept scipy-sparse end to end (disk + memory + the retriever's dot
  product) — a 10k x 4096 dense float32 matrix is ~160 MB, the sparse one a few MB.
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np

from mindbridge.config import VECTORS_DIR, settings
from mindbridge.features.embeddings import Embedder, make_tfidf_vectorizer

# How many cache entries to keep on disk (newest by mtime). Two corpora (jobs, candidates)
# times a couple of corpus revisions is the realistic working set.
MAX_ENTRIES = 16


def _l2_normalize_sparse(mat):
    """Row-normalize a scipy sparse matrix in place (zero rows left untouched)."""
    from sklearn.preprocessing import normalize

    return normalize(mat, norm="l2", copy=False)


class VectorStore:
    """Disk + in-memory cache for corpus embedding matrices.

    Call `corpus_vectors(texts)` first (loads or builds + persists), then `query_vector(text)`
    to embed a query consistently with that corpus. `enabled=None` follows the global setting;
    tests pass an explicit bool + a tmp cache_dir to stay hermetic.
    """

    def __init__(
        self,
        embedder: Embedder,
        cache_dir: Optional[Path] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.embedder = embedder
        self.cache_dir = Path(cache_dir) if cache_dir is not None else VECTORS_DIR
        self._enabled = enabled
        # key -> (matrix, fitted vectorizer | None). Tiny LRU: the working set is one corpus
        # per direction, so a handful of entries covers every request in a process.
        self._mem: dict[str, tuple[Any, Any]] = {}
        self._active_key: Optional[str] = None  # corpus the next query_vector pairs with

    @property
    def enabled(self) -> bool:
        return settings.vector_store if self._enabled is None else self._enabled

    # ---- keys -----------------------------------------------------------------------------

    def _backend_tag(self) -> str:
        tag = self.embedder.backend
        if tag == "sentence-transformers":
            # Different models -> different vector spaces; keep them apart.
            tag += "-" + settings.embed_model.replace("/", "-")
        return tag

    def _key(self, texts: list[str]) -> str:
        h = hashlib.sha256()
        for t in texts:
            h.update(t.encode("utf-8", "ignore"))
            h.update(b"\x00")  # unambiguous document boundary
        return f"{self._backend_tag()}-{h.hexdigest()[:16]}"

    # ---- disk I/O -------------------------------------------------------------------------

    def _paths(self, key: str) -> tuple[Path, Path, Path]:
        base = self.cache_dir / key
        return (
            base.with_suffix(".npz"),  # dense matrix (transformer)
            base.with_suffix(".sparse.npz"),  # sparse matrix (tfidf)
            base.with_suffix(".vectorizer.pkl"),  # fitted TF-IDF vectorizer
        )

    def _load(self, key: str) -> Optional[tuple[Any, Any]]:
        dense_p, sparse_p, vec_p = self._paths(key)
        try:
            if sparse_p.exists():
                from scipy import sparse

                matrix = sparse.load_npz(sparse_p)
                with vec_p.open("rb") as fh:
                    vectorizer = pickle.load(fh)
                return matrix, vectorizer
            if dense_p.exists():
                with np.load(dense_p) as data:
                    return data["vectors"], None
        except Exception:
            # Corrupt/partial cache entry -> behave like a miss and rebuild over it.
            return None
        return None

    def _save(self, key: str, matrix: Any, vectorizer: Any) -> None:
        dense_p, sparse_p, vec_p = self._paths(key)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            if vectorizer is not None:
                from scipy import sparse

                sparse.save_npz(sparse_p, matrix)
                with vec_p.open("wb") as fh:
                    pickle.dump(vectorizer, fh)
            else:
                np.savez_compressed(dense_p, vectors=matrix)
            self._prune()
        except Exception:
            # A failed write only costs us the warm start, never the request.
            pass

    def _prune(self) -> None:
        """Keep the newest MAX_ENTRIES matrices; drop older ones and their sidecars."""
        entries = sorted(
            [p for p in self.cache_dir.glob("*.npz")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in entries[MAX_ENTRIES:]:
            # `x.sparse.npz` -> strip both suffixes to get the key base.
            base = stale.with_suffix("")
            if base.suffix == ".sparse":
                base = base.with_suffix("")
            for p in (stale, base.with_suffix(".vectorizer.pkl")):
                p.unlink(missing_ok=True)

    # ---- public API -----------------------------------------------------------------------

    def corpus_vectors(self, texts: list[str]):
        """Return the L2-normalized embedding matrix for `texts`, from cache when possible."""
        key = self._key(texts)
        self._active_key = key

        if key in self._mem:
            return self._mem[key][0]

        loaded = self._load(key)
        if loaded is not None:
            self._remember(key, *loaded)
            return loaded[0]

        # Miss -> build. TF-IDF fits its own corpus-only vectorizer (persisted so queries can
        # be transformed against the same vocabulary on a warm start); other backends are
        # stateless and just encode.
        if self.embedder.backend == "tfidf":
            vectorizer = make_tfidf_vectorizer()
            matrix = _l2_normalize_sparse(vectorizer.fit_transform(texts))
        else:
            vectorizer = None
            matrix = self.embedder.encode(texts)

        self._save(key, matrix, vectorizer)
        self._remember(key, matrix, vectorizer)
        return matrix

    def query_vector(self, text: str) -> np.ndarray:
        """Embed one query consistently with the last `corpus_vectors` call."""
        if self.embedder.backend == "tfidf":
            entry = self._mem.get(self._active_key or "")
            if entry is None or entry[1] is None:
                # No fitted vocabulary to transform against — caller falls back to joint encode.
                raise RuntimeError("query_vector() requires a prior corpus_vectors() call")
            vec = _l2_normalize_sparse(entry[1].transform([text]))
            return np.asarray(vec.todense(), dtype=np.float32).ravel()
        return self.embedder.encode([text])[0]

    def _remember(self, key: str, matrix: Any, vectorizer: Any) -> None:
        self._mem[key] = (matrix, vectorizer)
        while len(self._mem) > 4:  # bound process memory; oldest insertion goes first
            self._mem.pop(next(iter(self._mem)))
