# Contributing

Thanks for looking under the hood. This file is the practical companion to
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — read that first for the *why*; this is the *how*.

## Dev setup

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt        # everything needed for dev + tests
cp .env.example .env                   # optional; defaults run offline

# frontend
cd frontend && npm install
```

Two processes during development:

```bash
python -m mindbridge.cli serve --reload    # API on :8000 (set MINDBRIDGE_CORPUS_LIMIT=200 for fast startup)
cd frontend && npm run dev                 # SPA on :5173, /api/* proxied to :8000
```

## Tests

```bash
pytest                                  # full suite — offline, no keys, no network
pytest tests/test_web.py                # one file
pytest tests/test_web.py::test_health   # one test
```

Ground rules the suite relies on:

- **Offline always.** Tests force the TF-IDF embedder (`tests/conftest.py`); OAuth tests stub
  the provider network calls. Never add a test that needs the internet or real keys.
- **Hermetic persistence.** Web tests override `get_db` with a throwaway SQLite file per test
  and skip the app lifespan. Don't touch `data/mindbridge.db` from a test.
- New behavior ships with tests — pattern-match the existing files.

Frontend: `npm run typecheck` must pass; `npm run build` is the real gate (tsc + Vite).

## Style

No lint/format config on the Python side by choice — match the existing style:

- Type hints everywhere, `from __future__ import annotations` at the top.
- Module-level docstrings explain **why**, not just what. Comments earn their place.
- Graceful degradation: one bad input (unreadable file, dead source, failed provider) degrades
  quietly, never crashes a run.
- Config comes only from the `settings` singleton (`mindbridge/config.py`); never read
  `os.environ` elsewhere. Note some env vars use a `MINDBRIDGE_` prefix wired manually in
  `config._load()`.

Frontend: TypeScript strict, one API client (`src/lib/api.ts`), types mirrored from the
backend in `src/types.ts` — update both sides in the same change.

## How to extend things (recipes)

**Add a data source.** Implement the base interface in `mindbridge/ingestion/` (see
`sample_source.py`), register it as one dict entry in `registry.py`, add a test. Sources must
normalize into `JobPosting`/`CandidateProfile` and fail quietly.

**Grow skill extraction.** Add terms to `SKILL_VOCAB` in `parsing/text_clean.py` — everything
downstream keys off skills, so this directly improves match quality. Add a case to
`tests/test_ingestion.py`-style extraction tests.

**Add a structured feature.** Update, in lockstep: `FEATURE_NAMES` +
`compute_structured_features` (`features/structured.py`), the heuristic weights
(`config.py` `w_*`), and retrain (`python -m mindbridge.cli train`) — a stale
`models/reranker.json` with the wrong feature count is refused at load (falls back to
heuristic), so retraining is not optional.

**Add an OAuth provider.** One `OAuthProvider` entry in `web/oauth.py`'s `PROVIDERS` dict +
two settings fields in `config.py` + `.env.example`. Routes, discovery, and the SPA buttons
all key off the dict. Stub the network calls in tests like the Google ones in `test_web.py`.

**Add an endpoint.** Router validates and delegates; anything engine-facing goes in
`web/services.py`. Request models in `dto.py`; responses reuse engine schemas where they fit.
Mirror the shape in `frontend/src/types.ts` + `lib/api.ts`.

## Hard rules

1. The engine (`mindbridge/` minus `web/`) never imports from `web/` — it stays importable and
   web-agnostic.
2. Components communicate only via the three schemas (`schemas.py`).
3. `FEATURE_NAMES`, the reranker vector, and the trained artifact move together.
4. A fresh clone with no keys and no network must pass the full test suite and serve matches.
5. The scraper stays **off by default** — scraping job boards violates most boards' ToS. Don't
   wire it into defaults.

## Commits / PRs

- Small, focused commits with imperative subjects ("Add GitHub OAuth provider", not "misc").
- If you change the API contract, update `docs/API.md` and `frontend/src/types.ts` in the same
  commit.
- Run `pytest` and `npm run build` before pushing.
