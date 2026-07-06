"""Parse the demo corpus markdown into domain objects.

The two demo zips (`demo_resumes_10000.zip`, `demo_job_descriptions_10000.zip`) hold highly
regular markdown. We read the *explicit* structured sections (Target Role, ## Skills, ## Required
Skills, ...) rather than running the free-text `extract_skills` heuristic over the body — the body
is identical boilerplate across every document, so heuristic extraction would inject false skills.

Two entry points, both tolerant of missing sections (return sensible defaults, never raise):
    parse_resume_markdown(text, doc_id) -> CandidateProfile
    parse_job_markdown(text, doc_id)    -> JobPosting
"""

from __future__ import annotations

import re

from mindbridge.schemas import CandidateProfile, JobPosting


def _first_h1(text: str) -> str:
    """The document title — the first `# Heading` line."""
    m = re.search(r"^\#\s+(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _kv(text: str, key: str) -> str:
    """A `Key: value` line (e.g. `Location: Chennai, India`). Case-insensitive key."""
    m = re.search(rf"^{re.escape(key)}\s*:\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _inline_field(text: str, label: str) -> str:
    """A bold inline field like `**Target Role:** Frontend Developer`."""
    m = re.search(rf"\*\*{re.escape(label)}\s*:\*\*\s*(.+?)\s*$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _section(text: str, header: str) -> str:
    """Raw body under a `## header`, up to the next `## ` heading (or EOF)."""
    m = re.search(
        rf"^\#\#\s+{re.escape(header)}\s*$\n(.*?)(?=^\#\#\s|\Z)",
        text,
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def _skills_from_section(body: str) -> list[str]:
    """Skills appear either comma-separated on one line (resumes) or as `- bullet` lines (jobs)."""
    if not body:
        return []
    bullets = re.findall(r"^\s*[-*]\s+(.+?)\s*$", body, re.MULTILINE)
    raw = bullets if bullets else body.split(",")
    # Return a comma string; the pydantic validator (_to_skill_list) cleans + lowercases + dedupes.
    return [s.strip() for s in raw if s.strip()]


def parse_resume_markdown(text: str, doc_id: str) -> CandidateProfile:
    """A demo `resume_NNNNN.md` -> CandidateProfile. `headline` carries the stated Target Role."""
    return CandidateProfile(
        id=doc_id,
        name=_first_h1(text),
        headline=_inline_field(text, "Target Role"),
        skills=_skills_from_section(_section(text, "Skills")),
        location=_kv(text, "Location"),
        resume_text=text,
        source="demo",
    )


def parse_job_markdown(text: str, doc_id: str) -> JobPosting:
    """A demo `job_description_NNNNN.md` -> JobPosting. Uses the `Reference ID` as the stable id."""
    ref = _kv(text, "Reference ID")
    return JobPosting(
        id=ref or doc_id,
        title=_first_h1(text),
        company=_kv(text, "Company"),
        location=_kv(text, "Location"),
        description=_section(text, "About the Role"),
        skills=_skills_from_section(_section(text, "Required Skills")),
        preferred_skills=_skills_from_section(_section(text, "Preferred Skills")),
        raw_text=text,
        source="demo",
    )
