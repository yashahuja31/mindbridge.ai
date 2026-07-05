"""MatchEngine — orchestrates the two-stage pipeline in both product directions.

    match_jobs_for_candidate(candidate, jobs, k)  -> best jobs for a hiree
    match_candidates_for_job(job, candidates, k)  -> best candidates for a hirer

Both do the same thing: stage-1 semantic retrieval narrows the field, stage-2 reranking scores
and explains each survivor, and we return the top-k `MatchResult`s sorted by final score.
"""

from __future__ import annotations

from mindbridge.config import settings
from mindbridge.matching.reranker import HeuristicReranker, get_reranker
from mindbridge.matching.retriever import SemanticRetriever
from mindbridge.schemas import CandidateProfile, JobPosting, MatchResult


class MatchEngine:
    def __init__(self, retriever: SemanticRetriever | None = None, reranker=None) -> None:
        self.retriever = retriever or SemanticRetriever()
        self.reranker = reranker or get_reranker()

    @property
    def embedder_backend(self) -> str:
        return self.retriever.embedder.backend

    @property
    def reranker_backend(self) -> str:
        return getattr(self.reranker, "backend", "unknown")

    def _retrieve_pool_size(self, k: int, corpus_size: int) -> int:
        """Stage-1 hands stage-2 a larger pool than k, so reranking can reorder meaningfully."""
        return min(corpus_size, max(k * settings.retrieve_multiplier, k))

    def match_jobs_for_candidate(
        self, candidate: CandidateProfile, jobs: list[JobPosting], k: int = 10
    ) -> list[MatchResult]:
        if not jobs:
            return []
        corpus = [j.matchable_text() for j in jobs]
        pool = self._retrieve_pool_size(k, len(jobs))
        retrieved = self.retriever.rank(candidate.matchable_text(), corpus, top_k=pool)

        results: list[MatchResult] = []
        for idx, sem in retrieved:
            job = jobs[idx]
            rr = self.reranker.score(candidate, job, sem)
            results.append(
                MatchResult(
                    subject_id=candidate.id,
                    matched_id=job.id,
                    matched_label=f"{job.title} @ {job.company}".strip(" @"),
                    score=rr.score,
                    semantic_score=sem,
                    rerank_score=rr.score,
                    reasons=rr.reasons,
                    feature_breakdown=rr.breakdown,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]

    def match_candidates_for_job(
        self, job: JobPosting, candidates: list[CandidateProfile], k: int = 10
    ) -> list[MatchResult]:
        if not candidates:
            return []
        corpus = [c.matchable_text() for c in candidates]
        pool = self._retrieve_pool_size(k, len(candidates))
        retrieved = self.retriever.rank(job.matchable_text(), corpus, top_k=pool)

        results: list[MatchResult] = []
        for idx, sem in retrieved:
            cand = candidates[idx]
            rr = self.reranker.score(cand, job, sem)
            results.append(
                MatchResult(
                    subject_id=job.id,
                    matched_id=cand.id,
                    matched_label=cand.name or cand.headline or cand.id,
                    score=rr.score,
                    semantic_score=sem,
                    rerank_score=rr.score,
                    reasons=rr.reasons,
                    feature_breakdown=rr.breakdown,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:k]
