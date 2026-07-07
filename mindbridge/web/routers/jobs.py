"""Job browsing routes — read-only listing/lookup over whatever sources are available."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from mindbridge.ingestion.registry import load_jobs
from mindbridge.schemas import JobPosting

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobPosting])
def list_jobs(
    q: str = Query("", description="Optional keyword filter"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sources: Optional[list[str]] = Query(None, description="e.g. sample, demo, api"),
) -> list[JobPosting]:
    """List jobs from the requested (or all available) sources, keyword-filtered and paginated."""
    jobs = load_jobs(query=q, sources=sources)
    return jobs[offset : offset + limit]


@router.get("/{job_id}", response_model=JobPosting)
def get_job(job_id: str, sources: Optional[list[str]] = Query(None)) -> JobPosting:
    """Fetch a single job by id, or 404."""
    for job in load_jobs(sources=sources):
        if job.id == job_id:
            return job
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No job with id '{job_id}'")
