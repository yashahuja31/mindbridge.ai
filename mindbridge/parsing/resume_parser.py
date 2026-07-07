"""Turn a resume file into plain text.

Supports .txt / .md (native), .pdf (pdfplumber), and .docx (docx2txt). Parsing libraries are
imported lazily so a missing optional dependency only affects that one format, and an unreadable
file yields "" rather than crashing an ingestion run.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def parse_resume_file(path: str | Path) -> str:
    """Extract text from a resume file. Returns "" if the format is unsupported or parsing fails."""
    path = Path(path)
    if not path.exists():
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix in (".txt", ".md", ""):
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            return _parse_pdf(path)
        if suffix in (".docx", ".doc"):
            return _parse_docx(path)
    except Exception:
        return ""
    return ""


def parse_resume_bytes(data: bytes, filename: str = "") -> str:
    """Extract text from in-memory resume bytes — the entry point for web uploads.

    Mirrors `parse_resume_file` (same format support, same never-crash contract) but takes raw
    bytes so an HTTP handler never has to persist the upload. `.txt`/`.md`/unknown are decoded
    directly; binary formats (.pdf/.docx) are written to a short-lived temp file and handed to the
    path-based parser, since pdfplumber/docx2txt want a real file. Returns "" on any failure.
    """
    if not data:
        return ""
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md", ""):
        return data.decode("utf-8", errors="ignore")
    # Binary formats: round-trip through a temp file so we reuse the exact path-based logic.
    # delete=False + explicit unlink because Windows can't reopen a still-open NamedTemporaryFile.
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        return parse_resume_file(tmp_path)
    except Exception:
        return ""
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _parse_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError:  # pragma: no cover
        return ""
    chunks: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def _parse_docx(path: Path) -> str:
    try:
        import docx2txt
    except ImportError:  # pragma: no cover
        return ""
    return docx2txt.process(str(path)) or ""
