"""Tests for the demo-corpus markdown parser (structured-section extraction, not heuristics)."""

from mindbridge.parsing.demo_markdown import parse_job_markdown, parse_resume_markdown

RESUME_MD = """# Riya Nair

**Target Role:** Software Engineer

Email: riya.nair1@example.com
Location: Chennai, India

## Summary
Motivated professional with experience in software development.

## Skills
HTML, React, Java, Docker, Machine Learning, Spring Boot

## Experience
Software Developer Intern
- Built internal tools.
"""

JOB_MD = """# Software Engineer

Company: BrightLogic
Location: Pune

## About the Role
We are looking for a motivated Software Engineer to build modern software.

## Required Skills
- Node.js
- Azure
- Docker

## Preferred Skills
- Java
- Go

Reference ID: JD-00001
"""


def test_parse_resume_extracts_core_fields():
    c = parse_resume_markdown(RESUME_MD, "resume_00001")
    assert c.id == "resume_00001"
    assert c.name == "Riya Nair"
    assert c.headline == "Software Engineer"  # from **Target Role:**
    assert c.location == "Chennai, India"
    assert c.source == "demo"
    assert c.resume_text == RESUME_MD


def test_parse_resume_skills_comma_separated_and_normalized():
    c = parse_resume_markdown(RESUME_MD, "resume_00001")
    # validator lowercases + dedupes; comma-separated Skills section is split
    assert "react" in c.skills
    assert "spring boot" in c.skills
    assert "machine learning" in c.skills


def test_parse_job_uses_reference_id_as_id():
    j = parse_job_markdown(JOB_MD, "job_description_00001")
    assert j.id == "JD-00001"  # Reference ID wins over the doc stem
    assert j.title == "Software Engineer"
    assert j.company == "BrightLogic"
    assert j.location == "Pune"
    assert j.source == "demo"


def test_parse_job_required_and_preferred_skills_from_bullets():
    j = parse_job_markdown(JOB_MD, "job_description_00001")
    assert "node.js" in j.skills and "docker" in j.skills
    assert "java" in j.preferred_skills and "go" in j.preferred_skills
    # required and preferred stay separate
    assert "java" not in j.skills


def test_parse_job_description_from_about_section():
    j = parse_job_markdown(JOB_MD, "job_description_00001")
    assert "motivated Software Engineer" in j.description
    # the About section stops before the next ## heading
    assert "Required Skills" not in j.description


def test_parser_tolerates_missing_sections():
    # a near-empty doc must not raise; fields fall back to sensible defaults
    c = parse_resume_markdown("# Someone\n", "resume_x")
    assert c.id == "resume_x"
    assert c.name == "Someone"
    assert c.headline == ""
    assert c.skills == []

    j = parse_job_markdown("# A Job\n", "job_x")
    assert j.id == "job_x"  # no Reference ID -> falls back to the stem
    assert j.title == "A Job"
    assert j.skills == []
