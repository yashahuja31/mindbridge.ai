"""MindBridge command-line interface.

    python -m mindbridge.cli match-jobs --resume path/to/resume.(txt|pdf|docx) --k 10
    python -m mindbridge.cli match-candidates --job-id j-002 --resumes data/sample/resumes --k 5
    python -m mindbridge.cli ingest --source sample
    python -m mindbridge.cli train

Everything works offline against the committed sample data with no API keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# Windows consoles often default to a legacy code page; force UTF-8 so output is clean.
try:  # pragma: no cover
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # pragma: no cover
    pass

from mindbridge.ingestion.registry import load_candidates, load_jobs
from mindbridge.matching.engine import MatchEngine
from mindbridge.parsing.resume_parser import parse_resume_file
from mindbridge.parsing.text_clean import extract_skills, guess_years_experience
from mindbridge.schemas import CandidateProfile, JobPosting

app = typer.Typer(add_completion=False, help="MindBridge.ai matching engine CLI")
console = Console()


def _candidate_from_resume(path: Path) -> CandidateProfile:
    text = parse_resume_file(path)
    if not text.strip():
        raise typer.BadParameter(f"Could not read any text from {path}")
    return CandidateProfile(
        id=path.stem,
        name=path.stem.replace("_", " ").title(),
        skills=extract_skills(text),
        years_experience=guess_years_experience(text),
        resume_text=text,
        source="cli",
    )


def _print_engine_banner(engine: MatchEngine) -> None:
    console.print(
        f"[dim]embedder: {engine.embedder_backend}  |  reranker: {engine.reranker_backend}[/dim]"
    )


def _results_table(title: str, rows) -> Table:
    table = Table(title=title, show_lines=True)
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Match", style="bold")
    table.add_column("Score", justify="right", style="green")
    table.add_column("Why", style="dim")
    for i, r in enumerate(rows, 1):
        why = "; ".join(r.reasons[:3]) if r.reasons else "-"
        table.add_row(str(i), r.matched_label or r.matched_id, f"{r.score:.3f}", why)
    return table


@app.command("match-jobs")
def match_jobs(
    resume: Path = typer.Option(..., exists=True, help="Path to a resume (.txt/.pdf/.docx)"),
    k: int = typer.Option(10, help="How many jobs to return"),
    query: str = typer.Option("", help="Optional keyword filter for job ingestion"),
    sources: Optional[str] = typer.Option(None, help="Comma-separated: sample,api,scraper"),
):
    """Recommend the best-fit jobs for a candidate's resume (the hiree flow)."""
    src = sources.split(",") if sources else None
    candidate = _candidate_from_resume(resume)
    jobs = load_jobs(query=query, sources=src)
    if not jobs:
        console.print("[yellow]No jobs found from the selected sources.[/yellow]")
        raise typer.Exit(1)

    engine = MatchEngine()
    _print_engine_banner(engine)
    results = engine.match_jobs_for_candidate(candidate, jobs, k=k)
    console.print(
        f"\n[bold]{candidate.name}[/bold] - {len(candidate.skills)} skills, "
        f"~{candidate.years_experience:.0f}y experience; scored against {len(jobs)} jobs\n"
    )
    console.print(_results_table(f"Top {len(results)} jobs", results))


@app.command("match-candidates")
def match_candidates(
    job_id: Optional[str] = typer.Option(None, help="Job id from the sample set (e.g. j-002)"),
    resumes: Path = typer.Option(
        Path("data/sample/resumes"), help="Folder of candidate resumes"
    ),
    k: int = typer.Option(10, help="How many candidates to return"),
):
    """Recommend the best-fit candidates for a job (the hirer flow)."""
    jobs = load_jobs(sources=["sample"])
    if not jobs:
        console.print("[yellow]No sample jobs available.[/yellow]")
        raise typer.Exit(1)
    job = next((j for j in jobs if j.id == job_id), jobs[0]) if job_id else jobs[0]

    candidates = _load_candidates_from_folder(resumes)
    if not candidates:
        console.print(f"[yellow]No resumes found in {resumes}.[/yellow]")
        raise typer.Exit(1)

    engine = MatchEngine()
    _print_engine_banner(engine)
    results = engine.match_candidates_for_job(job, candidates, k=k)
    console.print(
        f"\nHiring for [bold]{job.title} @ {job.company}[/bold] "
        f"({len(job.skills)} required skills); scored {len(candidates)} candidates\n"
    )
    console.print(_results_table(f"Top {len(results)} candidates", results))


def _load_candidates_from_folder(folder: Path) -> list[CandidateProfile]:
    if not folder.exists():
        return []
    out: list[CandidateProfile] = []
    for path in sorted(folder.glob("*")):
        if path.suffix.lower() not in (".txt", ".md", ".pdf", ".docx", ".doc"):
            continue
        try:
            out.append(_candidate_from_resume(path))
        except typer.BadParameter:
            continue
    return out


@app.command("ingest")
def ingest(
    source: str = typer.Option("sample", help="sample | api | scraper"),
    query: str = typer.Option("", help="Optional keyword filter"),
    limit: int = typer.Option(20, help="Max rows to show"),
):
    """Show what a data source returns (useful for checking API keys / the scraper flag)."""
    jobs = load_jobs(query=query, sources=[source], limit_per_source=limit)
    console.print(f"[bold]{len(jobs)}[/bold] job(s) from source '{source}':")
    table = Table(show_lines=False)
    table.add_column("id", style="cyan")
    table.add_column("title", style="bold")
    table.add_column("company")
    table.add_column("location", style="dim")
    for j in jobs[:limit]:
        table.add_row(j.id, j.title, j.company, j.location)
    console.print(table)


@app.command("build-corpus")
def build_corpus_cmd(
    force: bool = typer.Option(False, "--force", help="Rebuild even if the cache exists"),
    limit: Optional[int] = typer.Option(None, help="Only parse the first N docs per side (dev)"),
):
    """Parse the two demo zips into the processed parquet/JSONL cache (data/processed/)."""
    from mindbridge.ingestion.corpus_build import build_corpus

    console.print("[dim]Building demo corpus from zips (reads straight from the archives)...[/dim]")
    stats = build_corpus(force=force, limit=limit)
    action = "rebuilt" if stats.get("rebuilt") else "loaded from cache"
    console.print(
        f"[green]Corpus {action}:[/green] {stats['jobs']} jobs, {stats['candidates']} candidates."
    )


@app.command("train")
def train(
    scaled: bool = typer.Option(
        False, "--scaled", help="Train on the full demo corpus (honest metrics) vs. sample data"
    ),
):
    """Train the XGBoost reranker and save models/reranker.json (+ reranker_metrics.json)."""
    if scaled:
        from mindbridge.training.train_reranker import train_on_corpus

        console.print("[dim]Training reranker on the 10k demo corpus (proxy labels)...[/dim]")
        metrics = train_on_corpus(save=True)
    else:
        from mindbridge.training.train_reranker import train as _train

        console.print("[dim]Training reranker (weak labels at cold start)...[/dim]")
        metrics = _train(save=True)
    for key, value in metrics.items():
        console.print(f"  {key}: {value}")
    console.print("[green]Done. The engine will now use the trained model automatically.[/green]")


if __name__ == "__main__":
    app()
