"""Turn a resume file into plain text.

Supports .txt / .md (native), .pdf (pdfplumber), and .docx (docx2txt). Parsing libraries are
imported lazily so a missing optional dependency only affects that one format, and an unreadable
file yields "" rather than crashing an ingestion run.
"""

from __future__ import annotations

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
