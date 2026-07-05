"""Lightweight text normalization + heuristic extraction of skills and experience.

This is deliberately dependency-free and rule-based. It's the cold-start stand-in for a proper
skills taxonomy / NER model — good enough to drive structured matching features today, easy to
swap for something learned later.
"""

from __future__ import annotations

import re

# A pragmatic seed vocabulary. Extend freely — everything downstream keys off skills, so growing
# this list directly improves match quality. Multi-word phrases are checked as substrings.
SKILL_VOCAB: list[str] = [
    # languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust", "ruby",
    "php", "scala", "kotlin", "swift", "r", "matlab", "sql", "bash",
    # web / frontend
    "react", "angular", "vue", "next.js", "node.js", "node", "express", "django", "flask",
    "fastapi", "spring", "spring boot", "html", "css", "tailwind", "redux",
    # data / ml
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow",
    "scikit-learn", "sklearn", "xgboost", "catboost", "lightgbm", "pandas", "numpy", "spark",
    "hadoop", "airflow", "data engineering", "etl", "tableau", "power bi", "statistics",
    # cloud / devops
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "jenkins", "linux",
    "git", "microservices", "rest", "graphql", "kafka", "redis", "postgresql", "mysql",
    "mongodb", "elasticsearch",
    # roles / domains
    "product management", "project management", "agile", "scrum", "ux", "ui", "figma",
    "marketing", "sales", "seo", "finance", "accounting", "hr", "recruiting", "customer success",
    "cybersecurity", "penetration testing", "devops", "backend", "frontend", "full stack",
    "full-stack", "mobile", "android", "ios", "data science", "data analysis",
]

_WS_RE = re.compile(r"\s+")
# Match phrases like "5 years", "5+ years", "3-5 years of experience".
_YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?", re.IGNORECASE)


def normalize(text: str) -> str:
    """Collapse whitespace and lowercase — the canonical form used for matching."""
    return _WS_RE.sub(" ", (text or "").strip()).lower()


def extract_skills(text: str) -> list[str]:
    """Find known skills mentioned in `text`. Word-boundary aware for short tokens so 'r' or 'go'
    don't match inside other words; substring match for multi-word phrases."""
    low = normalize(text)
    found: list[str] = []
    for skill in SKILL_VOCAB:
        if " " in skill or "." in skill or "+" in skill or "#" in skill or "/" in skill:
            hit = skill in low
        else:
            hit = re.search(rf"\b{re.escape(skill)}\b", low) is not None
        if hit and skill not in found:
            found.append(skill)
    return found


def guess_years_experience(text: str) -> float:
    """Best-effort years-of-experience from resume text: the largest 'N years' figure found.
    Returns 0.0 if none is present."""
    matches = _YEARS_RE.findall(text or "")
    values = [float(m) for m in matches if m.isdigit()]
    # Cap at a sane ceiling so a stray "50 years" typo can't dominate features.
    return min(max(values), 45.0) if values else 0.0
