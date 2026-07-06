"""Abstract source interfaces. Every data source — sample, API, scraper — implements these,
so the rest of the system never cares where a job or resume came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from mindbridge.schemas import CandidateProfile, JobPosting


def text_filter(items: list, query: str, key: Callable) -> list:
    """Cheap case-insensitive substring filter shared by the offline sources.

    `key(item)` returns the searchable text for one item. Empty query -> everything.
    """
    q = (query or "").strip().lower()
    if not q:
        return items
    return [it for it in items if q in key(it).lower()]


class JobSource(ABC):
    """Produces `JobPosting`s. `query` is an optional free-text/role filter."""

    name: str = "base"

    @abstractmethod
    def fetch_jobs(self, query: str = "", limit: int = 100) -> list[JobPosting]:
        ...


class ResumeSource(ABC):
    """Produces `CandidateProfile`s (typically from resumes)."""

    name: str = "base"

    @abstractmethod
    def fetch_candidates(self, query: str = "", limit: int = 100) -> list[CandidateProfile]:
        ...
