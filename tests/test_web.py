"""M2 backend tests — exercise the FastAPI app end-to-end with a TestClient.

Everything runs offline against the committed `sample` source (the embedder auto-falls back to
TF-IDF with no torch). Persistence is hermetic: each test gets a throwaway SQLite database via a
`get_db` dependency override, and we deliberately do NOT enter the TestClient context manager so
the app's lifespan (which would create the real data/ database) never runs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mindbridge.web import models  # noqa: F401  (register tables on Base.metadata)
from mindbridge.web.app import app
from mindbridge.web.db import Base, get_db

SAMPLE = ["sample"]  # keep tests fast + offline; never touches the 10k demo corpus


@pytest.fixture
def client(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)  # no `with`: lifespan is skipped, tables come from the fixture above
    app.dependency_overrides.clear()
    engine.dispose()


def _auth_headers(client, email="a@b.com", password="secret123", role="hiree"):
    r = client.post("/auth/register", json={"email": email, "password": password, "role": role})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---- meta -------------------------------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "embedder" in body and "reranker" in body


# ---- auth -------------------------------------------------------------------------------------


def test_register_login_me(client):
    headers = _auth_headers(client, email="dev@example.com")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "dev@example.com"

    # login with the same creds returns a usable token
    login = client.post(
        "/auth/login", data={"username": "dev@example.com", "password": "secret123"}
    )
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_duplicate_registration_conflicts(client):
    _auth_headers(client, email="dup@example.com")
    r = client.post(
        "/auth/register", json={"email": "dup@example.com", "password": "secret123"}
    )
    assert r.status_code == 409


def test_bad_login_rejected(client):
    _auth_headers(client, email="x@example.com")
    r = client.post("/auth/login", data={"username": "x@example.com", "password": "wrong"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401


# ---- jobs -------------------------------------------------------------------------------------


def test_list_and_get_jobs(client):
    r = client.get("/jobs", params={"sources": SAMPLE, "limit": 5})
    assert r.status_code == 200
    jobs = r.json()
    assert len(jobs) >= 1
    job_id = jobs[0]["id"]

    one = client.get(f"/jobs/{job_id}", params={"sources": SAMPLE})
    assert one.status_code == 200
    assert one.json()["id"] == job_id

    assert client.get("/jobs/does-not-exist", params={"sources": SAMPLE}).status_code == 404


# ---- matching: hiree flow ---------------------------------------------------------------------

RESUME = (
    "Backend engineer with 6 years of experience in Python, Django, PostgreSQL, Docker and AWS. "
    "Built and scaled REST APIs and microservices."
)


def test_match_jobs_json(client):
    r = client.post("/match/jobs", json={"resume_text": RESUME, "k": 5, "sources": SAMPLE})
    assert r.status_code == 200, r.text
    results = r.json()
    assert 1 <= len(results) <= 5
    top = results[0]
    assert 0.0 <= top["score"] <= 1.0
    assert "reasons" in top and isinstance(top["reasons"], list)
    # results are sorted by score, descending
    scores = [x["score"] for x in results]
    assert scores == sorted(scores, reverse=True)


def test_match_jobs_upload(client):
    files = {"file": ("resume.txt", RESUME.encode("utf-8"), "text/plain")}
    r = client.post("/match/jobs/upload", files=files, data={"k": 3, "sources": "sample"})
    assert r.status_code == 200, r.text
    assert 1 <= len(r.json()) <= 3


def test_match_jobs_upload_empty_file_rejected(client):
    files = {"file": ("empty.txt", b"", "text/plain")}
    r = client.post("/match/jobs/upload", files=files, data={"sources": "sample"})
    assert r.status_code == 400


# ---- matching: hirer flow ---------------------------------------------------------------------


def test_match_candidates_by_id(client):
    jobs = client.get("/jobs", params={"sources": SAMPLE, "limit": 1}).json()
    job_id = jobs[0]["id"]
    r = client.post(
        "/match/candidates", json={"job_id": job_id, "k": 5, "sources": SAMPLE}
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 1


def test_match_candidates_by_text(client):
    r = client.post(
        "/match/candidates",
        json={
            "job_text": "Hiring a machine learning engineer skilled in Python, PyTorch and NLP.",
            "job_title": "Machine Learning Engineer",
            "k": 3,
            "sources": SAMPLE,
        },
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) >= 1


def test_match_candidates_requires_input(client):
    r = client.post("/match/candidates", json={"k": 5, "sources": SAMPLE})
    assert r.status_code == 400


# ---- history + persistence --------------------------------------------------------------------


def test_history_requires_auth(client):
    assert client.get("/match/history").status_code == 401


def test_history_persists_for_authenticated_user(client):
    headers = _auth_headers(client, email="hist@example.com")
    # anonymous run first — must NOT be saved to this user
    client.post("/match/jobs", json={"resume_text": RESUME, "k": 3, "sources": SAMPLE})
    # authenticated run — should be saved
    client.post(
        "/match/jobs", json={"resume_text": RESUME, "k": 3, "sources": SAMPLE}, headers=headers
    )

    hist = client.get("/match/history", headers=headers)
    assert hist.status_code == 200
    rows = hist.json()
    assert len(rows) == 1
    assert rows[0]["direction"] == "jobs"
    assert rows[0]["result_count"] >= 1
    assert isinstance(rows[0]["results"], list) and len(rows[0]["results"]) >= 1
