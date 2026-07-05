# MindBridge.ai

Two-sided job–talent matching. **Hirees** upload a resume and get their best-fit jobs; **hirers**
upload a job description + a folder of candidate resumes and get a ranked, *explained* shortlist.

The long-term goal is to match on more than keywords — role fit, company norms, and whether a
person is likely to actually be happy in the role — so companies get people who stay, and people
get jobs they don't burn out of.

> **Milestone 1 (this repo, right now): the matching engine core.** Pure Python, no web UI yet.
> The FastAPI backend and React hirer/hiree interfaces wrap this engine in later milestones.

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
  cli.py             typer CLI
data/sample/         small committed demo dataset
notebooks/           demo notebook
tests/               pytest suite
```

## Tests

```bash
pytest
```

## Roadmap

- **M1 (now):** matching engine core ✅
- **M2:** FastAPI backend + REST API around the engine
- **M3:** React hirer/hiree UIs, auth, resume upload, profile creation
- **M4:** live data ingestion at scale; persistent vector store
- **M5:** train the reranker on real outcome/satisfaction labels (the "fit" model)
