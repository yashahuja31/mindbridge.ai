"""Structured (non-semantic) match features between a candidate and a job.

These are the interpretable signals the stage-2 reranker blends with the semantic score, and the
same feature vector the trained XGBoost/CatBoost model consumes later. Every value is in [0, 1]
so weights stay comparable and the output is easy to explain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from mindbridge.schemas import CandidateProfile, JobPosting

# `taxonomy` is imported lazily inside compute_structured_features to avoid a circular import
# (features.structured <- matching.reranker <- matching package __init__). After the first call it's
# resolved from sys.modules, so the hot path pays only a dict lookup.

# Order matters: this is the exact feature-vector layout the trained model expects. `role_match`
# is APPENDED (not inserted) so the layout stays backward-compatible in position for the first five
# features; any add/reorder here must be matched by a model retrain (see CLAUDE.md).
FEATURE_NAMES = [
    "skill_coverage",
    "skill_overlap",
    "experience_match",
    "location_match",
    "salary_fit",
    "role_match",
]


@dataclass
class StructuredFeatures:
    skill_coverage: float = 0.0  # fraction of the JOB's required skills the candidate has
    skill_overlap: float = 0.0  # Jaccard of the two skill sets
    experience_match: float = 0.0  # how well candidate years fit the job's range
    location_match: float = 0.0  # same location or remote-compatible
    salary_fit: float = 0.0  # candidate's desired salary within the job's band
    role_match: float = 0.5  # role/title compatibility from the taxonomy (neutral default)
    # Extras used only for human-readable reasons (not fed to the model):
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)

    def vector(self) -> list[float]:
        d = asdict(self)
        return [float(d[name]) for name in FEATURE_NAMES]

    def as_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in FEATURE_NAMES}


def _experience_match(cand_years: float, job_min: float, job_max: float | None) -> float:
    """1.0 inside the job's range; decays as the candidate falls short or overshoots."""
    if cand_years >= job_min and (job_max is None or cand_years <= job_max):
        return 1.0
    if cand_years < job_min:
        gap = job_min - cand_years
        return max(0.0, 1.0 - gap / 5.0)  # -1.0 per year short, floored at 0
    # overshoot (over-qualified) — mild penalty
    assert job_max is not None
    over = cand_years - job_max
    return max(0.3, 1.0 - over / 15.0)


def _location_match(cand: CandidateProfile, job: JobPosting) -> float:
    if job.remote and cand.open_to_remote:
        return 1.0
    c, j = (cand.location or "").strip().lower(), (job.location or "").strip().lower()
    if not c or not j:
        return 0.5  # unknown -> neutral
    if c == j:
        return 1.0
    # city/country token overlap (e.g. "London, UK" vs "UK")
    if set(c.replace(",", " ").split()) & set(j.replace(",", " ").split()):
        return 0.7
    return 0.2


def _salary_fit(desired: float | None, job_min: float | None, job_max: float | None) -> float:
    if desired is None or (job_min is None and job_max is None):
        return 0.5  # unknown -> neutral
    lo = job_min if job_min is not None else 0.0
    hi = job_max if job_max is not None else float("inf")
    if lo <= desired <= hi:
        return 1.0
    if desired < lo:
        return 0.8  # cheaper than budget — fine for the employer
    # desired above the band: decays with how far over
    over_ratio = (desired - hi) / max(hi, 1.0)
    return max(0.0, 1.0 - over_ratio)


def compute_structured_features(cand: CandidateProfile, job: JobPosting) -> StructuredFeatures:
    from mindbridge.matching import taxonomy  # lazy: see import note at top of module

    cand_skills = set(cand.skills)
    job_skills = set(job.skills)

    matched = sorted(cand_skills & job_skills)
    missing = sorted(job_skills - cand_skills)

    coverage = len(matched) / len(job_skills) if job_skills else 0.5
    union = cand_skills | job_skills
    overlap = len(cand_skills & job_skills) / len(union) if union else 0.0

    return StructuredFeatures(
        skill_coverage=coverage,
        skill_overlap=overlap,
        experience_match=_experience_match(cand.years_experience, job.min_experience, job.max_experience),
        location_match=_location_match(cand, job),
        salary_fit=_salary_fit(cand.desired_salary, job.salary_min, job.salary_max),
        role_match=taxonomy.role_match(cand.headline, job.title),
        matched_skills=matched,
        missing_skills=missing,
    )
