# MindBridge.ai

Two-sided job–talent matching. **Hirees** upload a resume and get their best-fit jobs; **hirers**
upload a job description + a folder of candidate resumes and get a ranked, *explained* shortlist.

The long-term goal is to match on more than keywords — role fit, company norms, and whether a
person is likely to actually be happy in the role — so companies get people who stay, and people
get jobs they don't burn out of.

> **Milestones 1–2 are done.** The matching engine core (M1) is now wrapped by a **FastAPI
> backend** (M2) that serves both matching directions over HTTP, with accounts, resume upload,
> and saved match history. React hirer/hiree interfaces (M3) come next. See [`docs/API.md`](docs/API.md)
> for the full endpoint reference.

## How it works (the hybrid pipeline)

```
resume / job text
        │
        ▼
  [ parsing ]  PDF/DOCX/txt → clean text + extracted skills
        │
        ▼
  [ Stage 1: retriever ]   semantic embeddings → cosine similarity → top-K candidates
        │                  (sentence-transformers, falls back to TF-IDF offline)
        ▼
  [ Stage 2: reranker ]    structured features (skill overlap, experience gap, location,
        │                  salary fit) + semantic score → final score + human-readable reasons
        ▼
  ranked MatchResult[]  (score in [0,1] + "why this match")
```

Stage 2 starts as a **transparent weighted heuristic** (needs no training data). Once we collect
outcome labels (who was hired and stayed happy), `mindbridge/training/train_reranker.py` trains an
XGBoost/CatBoost model that the reranker loads automatically — no code change at the call site.

## Setup

```bash
cd mindbridge.ai
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — only needed for live job APIs
```

The first run downloads the embedding model (~90 MB). If that fails or you're offline, the engine
automatically falls back to a TF-IDF embedder so everything still works.

## Try it (offline, no API keys)

```bash
# Best jobs for a candidate's resume
python -m mindbridge.cli match-jobs --resume data/sample/resumes/backend_engineer.txt --k 5

# Best candidates for a job posting
python -m mindbridge.cli match-candidates --job data/sample/jobs.csv --job-id j-002 \
    --resumes data/sample/resumes --k 5

# List what the enabled data sources return
python -m mindbridge.cli ingest --source sample
```

Or open `notebooks/01_matching_engine_demo.ipynb` for the full walkthrough.

## Run the API (M2)

The same engine is served over HTTP by a FastAPI app. Start it with the CLI:

```bash
python -m mindbridge.cli serve                 # http://127.0.0.1:8000
python -m mindbridge.cli serve --reload        # dev mode, auto-reload on edits
# or directly:  uvicorn mindbridge.web.app:app --reload
```

Then open **http://127.0.0.1:8000/docs** for the interactive Swagger explorer. A quick smoke test:

```bash
# Best jobs for a pasted resume (anonymous, sample source only = fast + offline)
curl -s http://127.0.0.1:8000/match/jobs \
  -H "Content-Type: application/json" \
  -d '{"resume_text":"Backend engineer, 6y Python, Django, PostgreSQL, Docker, AWS","k":5,"sources":["sample"]}'
```

Endpoints at a glance (full details in [`docs/API.md`](docs/API.md)):

| Method & path            | Auth      | What it does |
|--------------------------|-----------|--------------|
| `GET  /health`           | –         | Liveness + which embedder/reranker backends are active |
| `POST /auth/register`    | –         | Create an account, returns a bearer token |
| `POST /auth/login`       | –         | OAuth2 password grant (`username` = email) → token |
| `GET  /auth/me`          | required  | Validate token / return the current user |
| `GET  /jobs`             | –         | List jobs from the enabled sources (filter, paginate) |
| `GET  /jobs/{job_id}`    | –         | Fetch one job, or 404 |
| `POST /match/jobs`       | optional  | Hiree flow: resume text → best-fit jobs |
| `POST /match/jobs/upload`| optional  | Hiree flow: upload `.txt/.md/.pdf/.docx` → best-fit jobs |
| `POST /match/candidates` | optional  | Hirer flow: a job (id or pasted text) → best candidates |
| `GET  /match/history`    | required  | The signed-in user's saved runs, newest first |

Matching endpoints work **anonymously**; if a valid token is sent, the run is also saved to that
user's history. Persistence is a small SQLite database (`data/mindbridge.db`, gitignored), created
automatically on first startup.

> **Tip:** the full 10k demo corpus makes server startup slow. Set `MINDBRIDGE_CORPUS_LIMIT=200`
> (or pass `"sources":["sample"]` per request) for a fast-starting dev server.

## Data sources

All three sources plug into one interface (`mindbridge/ingestion/`):

| Source   | Status        | Notes |
|----------|---------------|-------|
| `sample` | ✅ implemented | Committed demo data in `data/sample/`. Offline, no keys. |
| `api`    | ✅ implemented | Adzuna official API. Needs `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` in `.env`. |
| `scraper`| ⚠️ scaffold    | **Disabled by default.** Scraping LinkedIn/Naukri/Glassdoor violates their ToS and carries legal risk. Only exists so the architecture is complete; enable per-source at your own risk with `MINDBRIDGE_ENABLE_SCRAPER=1`. |

## Layout

```
mindbridge/          core package (importable)
  schemas.py         JobPosting, CandidateProfile, MatchResult
  ingestion/         pluggable data sources + registry
  parsing/           resume → text, skill extraction
  features/          embeddings (+ TF-IDF fallback), structured features
  matching/          retriever, reranker, engine  ← the two-stage pipeline
  training/          label generation + reranker training
  web/               FastAPI backend (M2): app, routers, auth, ORM, services
  cli.py             typer CLI (incl. `serve`)
data/sample/         small committed demo dataset
docs/                API reference (docs/API.md)
notebooks/           demo notebook
tests/               pytest suite
```

## Tests

```bash
pytest
```

## Roadmap

- **M1:** matching engine core ✅
- **M2:** FastAPI backend + REST API around the engine ✅ (accounts, upload, match history)
- **M3 (next):** React hirer/hiree UIs, resume upload UI, profile creation
- **M4:** live data ingestion at scale; persistent vector store
- **M5:** train the reranker on real outcome/satisfaction labels (the "fit" model)
