"""Role taxonomy — a small, auditable table that turns free-text job titles / resume headlines
into a `role_match` signal in [0, 1].

Why this exists: in the demo corpus the stated **role** (resume "Target Role", job title) is one of
the only real signals — the skill lists are randomly assigned, and there are no experience/salary
fields. So role compatibility carries real weight in the reranker. We keep it as a pure data table
(aliases + a symmetric compatibility matrix) rather than a model so it's transparent and testable.

    canonicalize("Sr. Frontend Engineer") -> "frontend_developer"
    role_match("Data Analyst", "Data Scientist") -> 0.75

Design:
  * 1.0  exact canonical match
  * COMPAT[a][b]  for known adjacent roles (e.g. data_analyst <-> data_scientist)
  * 0.5  otherwise (unknown role, or two known roles with no declared adjacency) — neutral, so an
         unrecognized title never zeroes out a match on its own.
The matrix deliberately bridges the corpus's job-only roles (Data Scientist, DevOps Engineer,
Product Manager, Business Analyst) to the resume roles so cross-side matches score sensibly.
"""

from __future__ import annotations

import re

# Canonical role keys. Everything the taxonomy understands maps to one of these.
CANONICAL_ROLES: list[str] = [
    "software_engineer",
    "backend_developer",
    "frontend_developer",
    "full_stack_developer",
    "ml_engineer",
    "data_scientist",
    "data_analyst",
    "qa_engineer",
    "devops_engineer",
    "product_manager",
    "business_analyst",
]

# Free-text -> canonical. Keys are matched against the normalized (lowercased) title as *substrings*
# after an exact-alias check, longest alias first, so "full stack developer" beats "developer".
ALIASES: dict[str, str] = {
    "software engineer": "software_engineer",
    "software developer": "software_engineer",
    "sde": "software_engineer",
    "programmer": "software_engineer",
    "backend developer": "backend_developer",
    "backend engineer": "backend_developer",
    "back end developer": "backend_developer",
    "server side developer": "backend_developer",
    "frontend developer": "frontend_developer",
    "frontend engineer": "frontend_developer",
    "front end developer": "frontend_developer",
    "ui developer": "frontend_developer",
    "full stack developer": "full_stack_developer",
    "full stack engineer": "full_stack_developer",
    "fullstack developer": "full_stack_developer",
    "full-stack developer": "full_stack_developer",
    "ml engineer": "ml_engineer",
    "machine learning engineer": "ml_engineer",
    "ai engineer": "ml_engineer",
    "mlops engineer": "ml_engineer",
    "data scientist": "data_scientist",
    "applied scientist": "data_scientist",
    "research scientist": "data_scientist",
    "data analyst": "data_analyst",
    "business intelligence analyst": "data_analyst",
    "bi analyst": "data_analyst",
    "analytics": "data_analyst",
    "qa engineer": "qa_engineer",
    "quality assurance": "qa_engineer",
    "test engineer": "qa_engineer",
    "sdet": "qa_engineer",
    "automation engineer": "qa_engineer",
    "devops engineer": "devops_engineer",
    "site reliability engineer": "devops_engineer",
    "sre": "devops_engineer",
    "platform engineer": "devops_engineer",
    "infrastructure engineer": "devops_engineer",
    "product manager": "product_manager",
    "product owner": "product_manager",
    "technical product manager": "product_manager",
    "business analyst": "business_analyst",
    "systems analyst": "business_analyst",
    "requirements analyst": "business_analyst",
}

# Symmetric compatibility for *adjacent* roles. Only off-diagonal, non-1.0 entries live here;
# exact matches are handled as 1.0 and everything else defaults to 0.5. Stored one-directional
# and mirrored at import time.
_COMPAT_SEED: dict[tuple[str, str], float] = {
    ("software_engineer", "backend_developer"): 0.85,
    ("software_engineer", "full_stack_developer"): 0.80,
    ("software_engineer", "frontend_developer"): 0.70,
    ("software_engineer", "devops_engineer"): 0.60,
    ("software_engineer", "qa_engineer"): 0.60,
    ("software_engineer", "ml_engineer"): 0.55,
    ("backend_developer", "full_stack_developer"): 0.85,
    ("backend_developer", "frontend_developer"): 0.55,
    ("backend_developer", "devops_engineer"): 0.65,
    ("backend_developer", "qa_engineer"): 0.55,
    ("frontend_developer", "full_stack_developer"): 0.85,
    ("frontend_developer", "qa_engineer"): 0.50,
    ("ml_engineer", "data_scientist"): 0.80,
    ("ml_engineer", "data_analyst"): 0.60,
    ("data_scientist", "data_analyst"): 0.75,
    ("data_scientist", "business_analyst"): 0.55,
    ("data_analyst", "business_analyst"): 0.65,
    ("product_manager", "business_analyst"): 0.70,
    ("product_manager", "data_analyst"): 0.45,
    ("devops_engineer", "full_stack_developer"): 0.55,
}

COMPAT: dict[str, dict[str, float]] = {r: {} for r in CANONICAL_ROLES}
for (_a, _b), _v in _COMPAT_SEED.items():
    COMPAT[_a][_b] = _v
    COMPAT[_b][_a] = _v

_ALIAS_KEYS_LONGEST_FIRST = sorted(ALIASES, key=len, reverse=True)
_WS_RE = re.compile(r"[\s/_-]+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", (text or "").strip().lower())


def canonicalize(text: str) -> str:
    """Map a free-text title/headline to a canonical role key, or "" if unrecognized."""
    norm = _normalize(text)
    if not norm:
        return ""
    if norm in ALIASES:
        return ALIASES[norm]
    # substring fallback, longest alias first (so "full stack developer" wins over "developer")
    for alias in _ALIAS_KEYS_LONGEST_FIRST:
        if alias in norm:
            return ALIASES[alias]
    return ""


def role_match(cand_role: str, job_role: str) -> float:
    """Compatibility of a candidate's role with a job's role, in [0, 1]."""
    a, b = canonicalize(cand_role), canonicalize(job_role)
    if not a or not b:
        return 0.5  # at least one side unrecognized -> neutral
    if a == b:
        return 1.0
    return COMPAT.get(a, {}).get(b, 0.5)
