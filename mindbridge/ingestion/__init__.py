"""Pluggable data ingestion: sample data, official APIs, and (scaffolded) scrapers."""

from mindbridge.ingestion.registry import load_candidates, load_jobs

__all__ = ["load_jobs", "load_candidates"]
