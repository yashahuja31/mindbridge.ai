# MindBridge.ai

**Two-sided job ⇄ talent matching that explains itself.**

**Hirees** paste or upload a resume and get their best-fit jobs; **hirers** describe a role and
get a ranked candidate shortlist. Every result carries a **score, human-readable reasons, and a
feature-by-feature breakdown** — the explanation is the product, not just the number.

The long-term goal is to match on more than keywords — role fit, company norms, and whether a
person is likely to actually be happy in the role — so companies get people who stay, and people
get jobs they don't burn out of.

> **Milestones 1–3 are done:** the matching engine core (M1), the FastAPI backend with accounts,
> upload, and history (M2), and the React web app with saved profiles/postings and OAuth sign-in
> (M3). See the [roadmap](#roadmap).

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
  [ Stage 2: reranker ]    structured features (skill overlap, role compatibility, experience
        │                  gap, location, salary fit) + semantic score → final score + reasons
        ▼
  ranked MatchResult[]  (score in [0,1] + "why this match")
```

The same pipeline runs both directions — the query and the corpus just swap sides. Stage 2 starts
as a **transparent weighted heuristic** (needs no training data). Once outcome labels exist (who
was hired and stayed happy), `mindbridge/training/train_reranker.py` trains an XGBoost model that
the reranker loads automatically — no code change at the call site.

## Quickstart

Requires **Python 3.12+** and (for the UI) **Node 18+**. Everything below runs fully offline
with no API keys.

```bash
git clone <this-repo>
cd mindbridge.ai

# 1. Backend
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # optional — defaults work offline

# 2. Prove the engine works — no server needed
python -m mindbridge.cli match-jobs --resume data/sample/resumes/backend_engineer.txt --k 5

# 3. Run the API  →  http://127.0.0.1:8000/docs
python -m mindbridge.cli serve --reload

# 4. Run the UI   →  http://localhost:5173     (new terminal)
cd frontend
npm install
npm run dev
```

Paste any resume on the home page and hit **Find matching jobs** — no account needed. Create an
account (or sign in with Google/GitHub once configured — see [docs/AUTH.md](docs/AUTH.md)) to get
saved profiles, postings, and match history.

> **Embeddings:** out of the box the engine embeds with TF-IDF (fast, offline). For better
> semantic quality, `pip install -r requirements-optional.txt` (torch, ~2.5 GB) — the engine
> picks up sentence-transformers automatically and falls back if it ever can't load.

Prefer a notebook? `notebooks/01_matching_engine_demo.ipynb` walks the engine end-to-end.

## The web app

React + TypeScript SPA in [`frontend/`](frontend/) (Vite, Tailwind, light/dark theme):

- **Match** — the core, both directions, works signed-out. Paste/upload a resume → ranked jobs;
  paste a JD (or job id) → ranked candidates. Each result expands to its reasons + score meters.
- **Sign in** — email/password, plus **Continue with Google / GitHub** buttons that appear
  automatically when the backend has OAuth keys configured.
- **My profile / My postings** — hirees keep one saved matching profile; hirers keep any number
  of saved postings. Both get one-click matching, no re-pasting.
- **History** — every signed-in run is saved and can be re-opened with its full ranked results.

Details: [docs/FRONTEND.md](docs/FRONTEND.md).

## The API

Interactive docs live at **http://127.0.0.1:8000/docs** when the server is running. A quick
smoke test:

```bash
curl -s http://127.0.0.1:8000/match/jobs \
  -H "Content-Type: application/json" \
  -d '{"resume_text":"Backend engineer, 6y Python, Django, PostgreSQL, Docker, AWS","k":5,"sources":["sample"]}'
```

Endpoints at a glance (full reference in [`docs/API.md`](docs/API.md)):

| Method & path                  | Auth      | What it does |
|--------------------------------|-----------|--------------|
| `GET  /health`                 | –         | Liveness + which embedder/reranker backends are active |
| `POST /auth/register` / `login`| –         | Email/password accounts → bearer token |
| `GET  /auth/providers`         | –         | Which OAuth providers are configured |
| `GET  /auth/oauth/{p}/start`   | –         | Begin Google/GitHub sign-in (browser redirect) |
| `GET  /auth/me`                | required  | Validate token / current user |
| `GET  /jobs`, `/jobs/{id}`     | –         | Browse jobs from the enabled sources |
| `POST /match/jobs`             | optional  | Hiree flow: resume text → best-fit jobs |
| `POST /match/jobs/upload`      | optional  | Same, from an uploaded `.txt/.md/.pdf/.docx` |
| `POST /match/candidates`       | optional  | Hirer flow: a job (id or text) → best candidates |
| `GET/PUT/DELETE /profile` + `/profile/match`    | required | Hiree's saved profile + one-click match |
| `/postings` CRUD + `/postings/{id}/match`       | required | Hirer's saved postings + one-click match |
| `GET  /match/history`          | required  | The signed-in user's saved runs |

Matching endpoints work **anonymously**; with a valid token the run is also saved to history.
Persistence is a small SQLite database (`data/mindbridge.db`, gitignored), created automatically
on first startup.

> **Tip:** the full 10k demo corpus makes server startup slow. Set `MINDBRIDGE_CORPUS_LIMIT=200`
> (or pass `"sources":["sample"]` per request) for a fast-starting dev server.

## Authentication

Two ways in, one token out — every path ends in the same JWT, so the rest of the API doesn't
care how you signed in:

- **Email + password** — always available, zero config. bcrypt-hashed, HS256 JWTs.
- **OAuth (Google / GitHub)** — enabled by setting a provider's client id + secret in `.env`;
  the SPA discovers configured providers at runtime and shows one button per provider. No keys,
  no buttons, no attack surface.

Set-up walkthroughs (including where to click in the Google/GitHub consoles) and the design
notes (why not a hosted provider like Clerk, and how to swap one in): **[docs/AUTH.md](docs/AUTH.md)**.

## Data sources

All sources plug into one interface (`mindbridge/ingestion/`) and are merged + deduped at load:

| Source   | Status        | Notes |
|----------|---------------|-------|
| `sample` | ✅ implemented | Committed demo data in `data/sample/`. Offline, no keys. |
| `demo`   | ✅ implemented | 10k resumes + 10k JDs, read straight from committed zips; parsed once into a local cache. |
| `api`    | ✅ implemented | Adzuna official API. Needs `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` in `.env`. |
| `scraper`| ⚠️ scaffold    | **Disabled by default.** Scraping LinkedIn/Naukri/Glassdoor violates their ToS and carries legal risk. Only exists so the architecture is complete; enable at your own risk with `MINDBRIDGE_ENABLE_SCRAPER=1`. |

## Layout

```
mindbridge/          core package (importable, web-agnostic)
  schemas.py         JobPosting, CandidateProfile, MatchResult — the whole contract
  ingestion/         pluggable data sources + registry
  parsing/           resume → text, skill extraction, demo-corpus markdown
  features/          embeddings (+ TF-IDF fallback), structured features
  matching/          retriever, reranker, taxonomy, engine  ← the two-stage pipeline
  training/          label generation + reranker training
  web/               FastAPI backend: app, routers, services, ORM, JWT + OAuth
  cli.py             typer CLI (incl. `serve`)
frontend/            React SPA (Vite, TypeScript, Tailwind)
data/sample/         small committed demo dataset
docs/                architecture, API, auth, frontend guides
notebooks/           demo notebook
tests/               pytest suite — offline, hermetic SQLite per test
```

## Documentation

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | The pipeline in depth, schemas, pluggability contracts, design rules |
| [docs/API.md](docs/API.md) | Every HTTP endpoint with request/response examples |
| [docs/AUTH.md](docs/AUTH.md) | Auth model, Google/GitHub OAuth setup step-by-step, Clerk notes |
| [docs/FRONTEND.md](docs/FRONTEND.md) | SPA structure, dev proxy, build & deploy |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, tests, conventions, how to extend things |

## Tests

```bash
pytest        # entire suite — offline, no keys, forced TF-IDF
```

## Roadmap

- **M1:** matching engine core ✅
- **M2:** FastAPI backend + REST API around the engine ✅ (accounts, upload, match history)
- **M3:** React hirer/hiree UI, saved profiles & postings, OAuth sign-in ✅
- **M4:** live data ingestion at scale; persistent vector store — **store ✅** (stage-1
  embeddings cached on disk, keyed by corpus fingerprint; pre-warm with
  `python -m mindbridge.cli warm-vectors`); live-ingestion scale-out in progress
- **M5:** train the reranker on real outcome/satisfaction labels (the "fit" model) —
  `match_history` is already accumulating the raw material
- **M6 (future):** ANN-backed vector index (FAISS/hnswlib) behind the same retriever seam, so
  stage-1 search stays sub-linear as the corpus grows past the point where a dense matmul is
  cheap — the persistent vector store (M4) is the on-disk substrate this builds on.
