"""Tests for the role taxonomy — the transparent role_match signal used by the reranker."""

from mindbridge.matching import taxonomy
from mindbridge.matching.taxonomy import COMPAT, canonicalize, role_match


def test_canonicalize_exact_alias():
    assert canonicalize("Software Engineer") == "software_engineer"
    assert canonicalize("data analyst") == "data_analyst"


def test_canonicalize_is_case_and_separator_insensitive():
    # normalization lowercases and collapses /, -, _ and whitespace
    assert canonicalize("FULL-STACK  Developer") == "full_stack_developer"
    assert canonicalize("Front_End Developer") == "frontend_developer"


def test_canonicalize_substring_longest_first():
    # "full stack developer" must win over the shorter "developer"-style aliases
    assert canonicalize("Sr. Full Stack Developer, Payments") == "full_stack_developer"
    # a title that merely contains a known alias as a substring still resolves
    assert canonicalize("Lead Backend Engineer") == "backend_developer"


def test_canonicalize_unknown_returns_empty():
    assert canonicalize("Underwater Basket Weaver") == ""
    assert canonicalize("") == ""


def test_role_match_exact_is_one():
    assert role_match("Software Engineer", "software engineer") == 1.0


def test_role_match_adjacent_from_compat_table():
    # seeded adjacency: data_scientist <-> data_analyst = 0.75
    assert role_match("Data Analyst", "Data Scientist") == 0.75
    assert role_match("ML Engineer", "Data Scientist") == 0.80


def test_role_match_is_symmetric():
    assert role_match("Data Scientist", "Data Analyst") == role_match(
        "Data Analyst", "Data Scientist"
    )


def test_role_match_unknown_side_is_neutral():
    assert role_match("Software Engineer", "Underwater Basket Weaver") == 0.5
    assert role_match("", "Data Scientist") == 0.5


def test_role_match_known_but_non_adjacent_defaults_neutral():
    # two recognized roles with no declared adjacency fall back to 0.5
    assert role_match("QA Engineer", "Product Manager") == 0.5


def test_compat_matrix_mirrored_at_import():
    # every seeded pair is stored in both directions
    for a, row in COMPAT.items():
        for b, v in row.items():
            assert COMPAT[b][a] == v


def test_module_lazy_import_hook_available():
    # structured.py imports this lazily by name; guard the attribute it depends on
    assert hasattr(taxonomy, "role_match")
