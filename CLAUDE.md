# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MindBridge.ai is a two-sided job⇄talent matching engine. Same pipeline runs both directions:
hirees get best-fit jobs from a resume; hirers get a ranked, *explained* candidate shortlist.
The product's value is the *explanation* (`reasons` + `feature_breakdown`), not just the score.

**Milestones 1–3 are done: the matching engine core (M1, pure Python), the FastAPI backend
(M2 — accounts, resume upload, saved match history), and the React frontend + persistent
profiles/postings + OAuth sign-in (M3).** The engine stays importable and web-agnostic; the web
layer (`mindbridge/web/`) is a thin wrapper. Docs: `docs/API.md` (HTTP reference),
`docs/ARCHITECTURE.md` (design + invariants), `docs/AUTH.md` (auth model + OAuth setup),
`docs/FRONTEND.md` (SPA guide), `CONTRIBUTING.md` (dev workflow + extension recipes).

## Commands

Run everything from the repo root, inside the venv (`python -m venv .venv` then activate).

```bash
pip install -r requirements.txt          # first run downloads the embed model (~90 MB)

# CLI (all work offline against committed sample data, no API keys):
python -m mindbridge.cli match-jobs --resume data/sample/resumes/backend_engineer.txt --k 5
python -m mindbridge.cli match-candidates --job-id j-002 --resumes data/sample/resumes --k 5
python -m mindbridge.cli ingest --source sample         # inspect what a source returns
python -m mindbridge.cli train                          # train reranker -> models/reranker.json
python -m mindbridge.cli serve --reload                 # run the M2 API; docs at /docs

pytest                                   # full suite (forced offline, TF-IDF)
pytest tests/test_matching.py            # one file
pytest tests/test_matching.py::test_name # one test
```

There is no separate lint/format config; keep to the existing style (type hints, `from __future__
import annotations`, module-level docstrings explaining *why*).

## Architecture

**Three shared schemas are the whole contract** (`mindbridge/schemas.py`): `JobPosting`,
`CandidateProfile`, `MatchResult`. Every layer — ingestion, parsing, features, matching — speaks
only in these, so components stay decoupled. Both entities expose `matchable_text()` (the text
stage-1 embeds). All score fields are clamped to `[0, 1]` by validators.

**The two-stage pipeline** (`mindbridge/matching/engine.py` orchestrates):
1. **Retriever** (`retriever.py`) — embeds query + corpus, cosine similarity (a dot product since
   vectors are L2-normalized), returns top-K `(index, score)`. Maps cosine `[-1,1]`→`[0,1]`.
2. **Reranker** (`reranker.py`) — blends the semantic score with structured features into a final
   score + human-readable `reasons`.

`MatchEngine` is **direction-agnostic**: `match_jobs_for_candidate` and `match_candidates_for_job`
are the same logic with query/corpus swapped. Stage 1 hands stage 2 a pool larger than `k`
(`retrieve_multiplier`, default 5×) so reranking can meaningfully reorder.

**Two pluggable strategies, each hot-swapped by a factory — this is the core pattern to preserve:**
- Embedder (`features/embeddings.py`, `get_embedder()`): sentence-transformers primary, **auto-falls
  back to TF-IDF** on any import/network/load failure so the pipeline *always* runs. Process-wide
  singleton. Tests force TF-IDF (see `tests/conftest.py`) for speed + offline.
- Reranker (`get_reranker()`): `HeuristicReranker` (transparent weighted blend, the cold-start
  default, needs no training data) is replaced by `ModelReranker` (XGBoost) **automatically** the
  moment `models/reranker.json` exists — no call-site change. Corrupt/missing artifact → silently
  reverts to heuristic.

**The feature-vector contract is order-sensitive.** `FEATURE_NAMES` in `features/structured.py` is
the single source of truth for layout; the trained model consumes exactly `[*FEATURE_NAMES,
semantic_score]`. If you add/reorder a structured feature, `FEATURE_NAMES`, the reranker vector,
and training must stay in lockstep — retrain the model. Some fields on `StructuredFeatures`
(`matched_skills`, `missing_skills`) are for reasons only and deliberately *not* in the vector.

**Ingestion registry** (`ingestion/registry.py`): callers use `load_jobs()` / `load_candidates()`
and never touch a source directly. Adding a source is a one-line entry in the `_JOB_SOURCES` /
`_RESUME_SOURCES` dicts. Results dedupe by `id`; **a failing source is skipped, never fatal**
(wrapped in try/except by design). Default sources: `sample` always, `api` (Adzuna) only if keys
set, `scraper` only if explicitly enabled.

**Training** (`training/`): at cold start there are no real outcome labels, so `make_labels.py`
uses a **weak label = the heuristic's own score**. Training on that just distills the heuristic
(smoke test / scaffold, not a quality gain). Real `hired`/`satisfaction` labels drop in via the
`label` column with no other code change — that's the M5 payoff.

## Web layer (M2, `mindbridge/web/`)

A thin FastAPI wrapper; **all matching logic stays in the engine, reached only through
`web/services.py`**. Keep it that way — routers validate input and delegate, nothing engine-facing
belongs in a router. Layout:
- `app.py` — `create_app()` factory (CORS, `lifespan` calls `init_db()`, includes routers, `/health`
  reports `engine_info()`). Module-level `app` exists so `uvicorn mindbridge.web.app:app` and the
  `serve` CLI command work. (This Starlette version keeps included routers as `_IncludedRouter`
  entries in `app.routes` rather than flattening their `APIRoute`s — the endpoints are still live;
  don't be fooled into thinking they're unmounted.)
- `routers/` — `auth` (register/login/me + OAuth: `providers` discovery, `oauth/{p}/start`,
  `oauth/{p}/callback`), `jobs` (list/get), `match` (jobs, jobs/upload, candidates, history),
  `profile` (hiree profile + hirer postings CRUD + one-click match). Matching routes use
  `get_optional_user`: they serve anonymous callers but **persist history only when a valid
  token is present**.
- `oauth.py` — OAuth provider registry (Google/GitHub), mirroring the ingestion-registry
  pattern: one `PROVIDERS` dict entry per provider; a provider is live iff its client id +
  secret are configured (`GET /auth/providers` and the SPA's buttons key off this). `state` is
  a purpose-tagged short-lived JWT (stateless CSRF protection); account linking is by verified
  email only; tokens return to the SPA in the URL *fragment* (`/login#token=…`). OAuth-created
  users have `hashed_password = NULL` and password login for them returns a clear 400.
- `services.py` — the glue: builds `CandidateProfile`/`JobPosting` from raw text with the same
  heuristics as the CLI, resolves jobs, runs the pipeline, saves history. Holds a **process-wide
  singleton `MatchEngine`** (`get_engine()`).
- `dto.py` — request models, kept **separate from engine schemas** so the API can evolve
  independently; responses reuse `JobPosting`/`MatchResult` verbatim.
- `security.py` — bcrypt hashing (passwords truncated to bcrypt's 72-byte limit) + HS256 JWTs.
  `get_current_user` (401 on failure) vs `get_optional_user` (returns `None`, never raises).
- `db.py` / `models.py` — SQLAlchemy engine + `get_db` dependency; `User` and `MatchHistory` tables.
  Tests override `get_db` with a throwaway SQLite db and skip the lifespan, so nothing hard-codes prod.

Two engine changes M2 relies on: `parsing/resume_parser.parse_resume_bytes()` (parse an upload from
memory — text decoded directly, binary formats round-tripped through a temp file, never crashes) and
a **feature-count guard** in `ModelReranker` — it validates the artifact's feature count against the
current `FEATURE_NAMES` layout on load and raises so `get_reranker()` falls back to the heuristic
instead of blowing up at predict time (the documented "incompatible artifact → heuristic" behavior).

## Conventions & gotchas

- **Config**: import the `settings` singleton from `mindbridge/config.py` — one source of truth for
  weights, model name, API keys. `.env` is gitignored (`.env.example` is the template). Note the
  quirk: some env vars use a `MINDBRIDGE_` prefix, wired up manually in `config._load()`, not the
  default pydantic-settings mechanism.
- **Graceful degradation is a design rule, not an accident**: unreadable resume → `""`, missing
  optional parser dep → that format only fails, dead source → contributes nothing. Preserve this;
  don't let one bad input crash a run.
- **Skill extraction** (`parsing/text_clean.py`) is a rule-based seed vocab (`SKILL_VOCAB`), the
  cold-start stand-in for a real taxonomy/NER. Everything downstream keys off skills, so *growing
  `SKILL_VOCAB` directly improves match quality.* Multi-word/symbol skills match as substrings;
  short tokens use word boundaries.
- **Scraper is OFF by default** and ships as a scaffold only — scraping LinkedIn/Naukri/Glassdoor
  violates their ToS. Enable per-source at your own risk with `MINDBRIDGE_ENABLE_SCRAPER=1`.
- Sample data lives in `data/sample/` (`jobs.csv`, resumes as `.txt`); skills are `;`-separated in
  CSV and coerced to clean lowercase lists by `_to_skill_list` in schemas.

## Roadmap (context for where code is headed)

M1 engine core ✅ → M2 FastAPI backend around the engine ✅ (accounts, upload, match history) →
M3 React hirer/hiree UI + profiles/postings + OAuth ✅ → M4 (next) live ingestion at scale +
persistent vector store → M5 train the reranker on real outcome/satisfaction labels (the "fit"
model). The engine stays importable and web-agnostic — the frontend consumes the M2/M3 API, and
the `match_history` table is already the seed of M5's outcome labels.

## Frontend (M3, `frontend/`)

Vite + React 18 + TypeScript + Tailwind SPA. One typed API client (`src/lib/api.ts`, all calls
to `/api/*` — Vite dev-proxies to :8000); `src/types.ts` mirrors the backend contract and must
move in lockstep with `dto.py`/`schemas.py`. Auth state in `src/context/AuthContext.tsx`
(localStorage token validated against `/auth/me`; `loginWithToken` adopts OAuth fragment
tokens). Pages: Match (both directions, anonymous-friendly), Auth (password + OAuth buttons
from `/auth/providers`, consumes `/login#token=…`), Profile (hiree profile / hirer postings by
role), History. Build gate: `npm run build` (tsc + Vite).
