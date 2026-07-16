# Architecture

How MindBridge is put together, and — more importantly — **why**. If you change code here,
this file tells you which contracts you must not break.

## The one-paragraph version

MindBridge is a **two-stage matching pipeline** wrapped by a thin web layer. Three Pydantic
schemas (`JobPosting`, `CandidateProfile`, `MatchResult`) are the entire contract between
components. Stage 1 retrieves a candidate pool by embedding similarity; stage 2 reranks that
pool with structured features and produces the explanation. Every heavy or external dependency
(embedding model, trained reranker, data sources, OAuth providers) is behind a factory or
registry with a graceful fallback, so **the pipeline always runs** — offline, keyless, on a
fresh clone.

```
                       ┌────────────────────────────── mindbridge/ (importable, web-agnostic)
 CLI ──────────┐       │  ingestion/registry ── sample | demo | api | (scraper, off)
               ├──►  schemas.py  ◄─ parsing/ (pdf/docx/txt → text, skills, experience)
 FastAPI ──────┘       │
 (web/)                │  MatchEngine (matching/engine.py)
                       │    stage 1: retriever.py  — embed + cosine → top-K pool
                       │    stage 2: reranker.py   — features + semantic → score + reasons
                       │
                       │  features/embeddings.py   — sentence-transformers ⇄ TF-IDF
                       │  features/structured.py   — FEATURE_NAMES (order-sensitive!)
                       │  training/                — weak labels → XGBoost artifact
                       └──────────────────────────────
```

## The three schemas are the whole contract

`mindbridge/schemas.py` defines `JobPosting`, `CandidateProfile`, `MatchResult`. Every layer —
ingestion, parsing, features, matching, web — speaks **only** these. That's what keeps a CSV
row, a 10k-corpus markdown file, an Adzuna API response, and a pasted web form
indistinguishable to the engine.

- Both entities expose `matchable_text()` — the text stage 1 embeds.
- All score fields are clamped to `[0, 1]` by validators.
- `MatchResult` is direction-agnostic: `subject_id` is who we matched *for*, `matched_id` what
  was recommended. `reasons` (strings) + `feature_breakdown` (name → value) are the product.

## The two-stage pipeline

`MatchEngine` (`matching/engine.py`) orchestrates and is **direction-agnostic** —
`match_jobs_for_candidate` and `match_candidates_for_job` are the same logic with query and
corpus swapped.

**Stage 1 — retrieval** (`matching/retriever.py`). Embed query + corpus, L2-normalize, cosine
similarity (a dot product), return top-K `(index, score)` with cosine `[-1,1]` mapped to
`[0,1]`. K is `k × retrieve_multiplier` (default 5×) so stage 2 has room to meaningfully
reorder.

### The persistent vector store (M4)

Re-encoding the corpus per request is the scaling bottleneck: a running server re-ranks the
same 10k demo jobs on every match. `features/vector_store.py` caches corpus embedding matrices
on disk (`data/processed/vectors/`, gitignored) keyed by **(embedder backend [+ model name],
SHA-256 of the ordered corpus texts)** — so any change to corpus content, order, size, or the
embedder yields a new key. *A stale cache can never be served; it just stops being hit.*

- **TF-IDF is corpus-stateful**: query vectors must come from the same fitted vocabulary as
  the cached matrix, so the fitted vectorizer is persisted next to the vectors. The store fits
  on the corpus only and transforms queries against it (the storeless path fits jointly on
  corpus+query — scores shift a hair, ordering doesn't; `test_query_ranks_like_direct_encode`
  pins this). Matrices stay scipy-sparse end to end (a dense 10k×4096 float32 is ~160 MB).
- **Transformer embeddings are stateless**: only the matrix is cached; queries encode live.
- **Graceful degradation, as everywhere**: any cache read/write failure falls back to the
  original joint encode inside `SemanticRetriever._similarities()` — retrieval never breaks on
  a cache problem. Disable entirely with `MINDBRIDGE_VECTOR_STORE=0`.
- Pre-warm before first serve with `python -m mindbridge.cli warm-vectors`. Tests disable the
  store globally (`tests/conftest.py`) and re-enable it against `tmp_path`
  (`tests/test_vector_store.py`).

> **M6 (future):** the retriever computes similarities with a dense matmul (`matrix @ query`),
> which is fine at demo scale but goes linear in corpus size. An approximate-nearest-neighbor
> index (FAISS / hnswlib) drops in behind the same `SemanticRetriever._similarities()` seam,
> reading the persisted matrices this store already writes — so M4 is deliberately the substrate
> M6 builds on, not a throwaway.

**Stage 2 — rerank + explain** (`matching/reranker.py`). Compute structured features for each
pair, blend with the semantic score, sort, cut to `k`, and emit reasons. Two implementations
behind `get_reranker()`:

- `HeuristicReranker` — transparent weighted sum (weights in `config.py`, `w_*`). The
  cold-start default; needs no training data; every weight is inspectable.
- `ModelReranker` — XGBoost, **activated automatically** the moment `models/reranker.json`
  exists. Corrupt or feature-count-incompatible artifact → silently reverts to the heuristic
  (the artifact's feature count is validated against `FEATURE_NAMES` at load).

### The feature-vector contract (order-sensitive!)

`FEATURE_NAMES` in `features/structured.py` is the single source of truth for the vector
layout:

```python
["skill_coverage", "skill_overlap", "experience_match", "location_match", "salary_fit", "role_match"]
```

A trained model consumes exactly `[*FEATURE_NAMES, semantic_score]`. If you add or reorder a
feature: update `FEATURE_NAMES`, the feature computation, and **retrain the model** — the three
must move in lockstep. Some `StructuredFeatures` fields (`matched_skills`, `missing_skills`)
exist only to build reasons and are deliberately *not* in the vector.

## Pluggability — the pattern to preserve

Two strategies are hot-swapped by factories; **this is the core pattern of the codebase**:

| Seam | Factory | Primary | Fallback | Trigger |
|---|---|---|---|---|
| Embedder | `features/embeddings.get_embedder()` | sentence-transformers | TF-IDF | any import/network/load failure |
| Reranker | `matching/reranker.get_reranker()` | XGBoost artifact | weighted heuristic | artifact missing/corrupt/incompatible |

Both are process-wide singletons. Tests force TF-IDF (`tests/conftest.py`) for speed and
offline determinism.

The same shape recurs everywhere a third party is involved:

- **Ingestion registry** (`ingestion/registry.py`) — callers use `load_jobs()` /
  `load_candidates()`, never a source directly. Adding a source is one dict entry. Results
  dedupe by `id`; **a failing source is skipped, never fatal** (by design, wrapped in
  try/except). `sample` always on; `demo` auto-enabled when the corpus zips exist; `api`
  (Adzuna) only with keys; `scraper` only if explicitly enabled (ToS risk).
- **OAuth providers** (`web/oauth.py`) — one `PROVIDERS` dict entry per provider; a provider
  is live ⇔ its keys are configured; `GET /auth/providers` and the SPA's buttons key off it.

**Graceful degradation is a design rule, not an accident.** Unreadable resume → `""`; missing
optional parser dep → only that format fails; dead source → contributes nothing; no torch →
TF-IDF; no artifact → heuristic; no OAuth keys → password auth. Don't let one bad input crash
a run.

## Parsing & skills

`parsing/text_clean.py` extracts skills against a rule-based seed vocabulary (`SKILL_VOCAB`) —
the cold-start stand-in for a real taxonomy/NER. Everything downstream keys off skills, so
**growing `SKILL_VOCAB` directly improves match quality**. Multi-word/symbol skills match as
substrings; short tokens use word boundaries. `matching/taxonomy.py` adds role aliases and a
symmetric role-compatibility matrix (the `role_match` feature).

`parsing/resume_parser.py` turns `.txt/.md/.pdf/.docx` into text — from a path (CLI) or from
bytes in memory (web upload); binary formats round-trip through a temp file and never crash.

## Training (M5 scaffolding)

At cold start there are no outcome labels, so `training/make_labels.py` uses a **weak label:
the heuristic's own score**. Training on that only distills the heuristic — it's a smoke test
of the training path, not a quality gain. The payoff comes when real `hired`/`satisfaction`
labels drop into the `label` column with no other code change. `match_history` (web layer) is
already accumulating the raw material.

## The web layer (`mindbridge/web/`)

A deliberately thin FastAPI wrapper — **all matching logic stays in the engine**, reached only
through `web/services.py`:

```
routers/          validate input, delegate, shape responses — nothing engine-facing
  auth.py         register/login/me + OAuth (providers, start, callback)
  jobs.py         read-only job browsing
  match.py        both matching directions + upload + history
  profile.py      hiree profile (one) + hirer postings (many) + one-click match
services.py       the glue: text → schemas, engine runs, history persistence, singleton engine
dto.py            request models (web contract ≠ engine contract; responses reuse engine schemas)
security.py       bcrypt + JWT mint/verify; get_current_user (401) vs get_optional_user (None)
oauth.py          provider registry: authorize/token URLs, code exchange, verified-email fetch
models.py         ORM: User, Profile, Posting, MatchHistory
db.py             engine/session factory, init_db() (create_all + minimal in-place migrations)
```

Key decisions:

- **Anonymous-friendly matching.** Match routes use `get_optional_user`: they serve anonymous
  callers, and persist history only when a valid token is present.
- **DTOs are separate from engine schemas** so the API can evolve independently; responses
  reuse `JobPosting`/`MatchResult` verbatim because they're already the shape a UI wants.
- **One engine per process** (`services.get_engine()`), caching the embedder/reranker choice.
- **Auth converges on one JWT.** Password and OAuth both end in `create_access_token(user.id)`;
  nothing downstream knows the difference. See [AUTH.md](AUTH.md).
- **Tests are hermetic.** Each test overrides `get_db` with a throwaway SQLite file and skips
  the lifespan, so nothing hard-codes the prod database.

## The frontend (`frontend/`)

React 18 + TypeScript + Vite + Tailwind SPA. It consumes only the public API (`docs/API.md`)
through one typed client (`src/lib/api.ts`); `src/types.ts` mirrors the backend contract
one-to-one. Auth state lives in `src/context/AuthContext.tsx` (token in localStorage, validated
against `/auth/me` on load). In dev, Vite proxies `/api/*` → `:8000`, keeping calls same-origin.
See [FRONTEND.md](FRONTEND.md).

## Configuration

One source of truth: the `settings` singleton in `mindbridge/config.py` (pydantic-settings +
`.env`). Quirk to know: some env vars use a `MINDBRIDGE_` prefix wired up manually in
`config._load()` — check `.env.example` for the canonical names. Never read `os.environ`
elsewhere.

## Invariants — the short list

1. Components speak only the three schemas; sources/parsers normalize *into* them.
2. `FEATURE_NAMES`, the reranker vector, and the trained artifact move in lockstep.
3. Every external dependency has a working fallback; a fresh clone runs offline with no keys.
4. The engine never imports from `web/`; the web layer reaches the engine only via `services.py`.
5. A failing source/provider/parser degrades quietly, never fatally.
