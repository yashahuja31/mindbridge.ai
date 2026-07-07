# MindBridge.ai HTTP API (M2)

The M2 backend is a thin FastAPI wrapper around the M1 matching engine. It adds three things the
engine itself is deliberately without: **HTTP access**, **accounts**, and **persistence** (saved
match history). All matching logic still lives in the engine and is reached through
`mindbridge/web/services.py` — the web layer only validates input and shapes responses.

- Base URL (default): `http://127.0.0.1:8000`
- Interactive docs: **`/docs`** (Swagger UI) and `/redoc`
- OpenAPI schema: `/openapi.json`

## Running it

```bash
python -m mindbridge.cli serve                 # 127.0.0.1:8000
python -m mindbridge.cli serve --host 0.0.0.0 --port 8080
python -m mindbridge.cli serve --reload        # dev auto-reload
# equivalently:
uvicorn mindbridge.web.app:app --reload
```

On startup the app creates its SQLite tables (idempotent). The database file defaults to
`data/mindbridge.db` (gitignored); override with a `DATABASE_URL` env var (pydantic-settings reads
it by field name — note there's **no** `MINDBRIDGE_` prefix on this one).

> The full 10k demo corpus makes the first request slow because every source is loaded. For a
> snappy dev server set `MINDBRIDGE_CORPUS_LIMIT=200`, or pass `"sources": ["sample"]` on each
> matching request to stay on the small committed dataset.

## Authentication

Auth is **optional for matching** and **required for history**. It uses JWT bearer tokens
(HS256), signed with `settings.secret_key`.

1. `POST /auth/register` or `POST /auth/login` returns `{ "access_token": "...", "token_type": "bearer" }`.
2. Send it on subsequent requests as `Authorization: Bearer <token>`.

Tokens expire after `access_token_expire_minutes` (default 24h). **Set `MINDBRIDGE_SECRET_KEY` to a
long random value in production** — the built-in default is an obvious placeholder.

Matching endpoints accept requests with *or* without a token. With a valid token, the run is also
saved to that user's history; without one, the run is stateless.

---

## Endpoints

### Meta

#### `GET /` and `GET /health`

`/health` reports liveness and which engine backends are active — useful for confirming whether the
heavy `sentence-transformers` embedder loaded or the pipeline fell back to TF-IDF:

```json
{ "status": "ok", "embedder": "tfidf", "reranker": "heuristic" }
```

`embedder` is `sentence-transformers` or `tfidf`; `reranker` is `model` (trained XGBoost artifact
present) or `heuristic`.

### Auth

#### `POST /auth/register` → `201`

Body:
```json
{ "email": "dev@example.com", "password": "secret123", "role": "hiree" }
```
- `password` — min length 6.
- `role` — `"hiree"` (job seeker) or `"hirer"` (employer); defaults to `hiree`.
- Duplicate email → `409`. Returns a `Token` so the client is logged in immediately.

#### `POST /auth/login` → `200`

OAuth2 password grant — send **form-encoded** fields, not JSON:
```
username=dev@example.com&password=secret123
```
(`username` is the email.) Bad credentials → `401`. Returns a `Token`.

#### `GET /auth/me` → `200` *(auth required)*

Returns the current user `{ id, email, role, created_at }`. Missing/invalid token → `401`. Handy as
a token-validity probe.

### Jobs

#### `GET /jobs` → `200`

List jobs from the enabled sources.

| Query param | Default | Notes |
|-------------|---------|-------|
| `q`         | `""`    | Optional keyword filter |
| `limit`     | `20`    | 1–200 |
| `offset`    | `0`     | For pagination |
| `sources`   | all     | Repeatable, e.g. `?sources=sample&sources=demo` |

Returns a list of `JobPosting`.

#### `GET /jobs/{job_id}` → `200`

Fetch one job by id, or `404`. Accepts the same `sources` query param.

### Matching

All three return a **sorted (desc by `score`) list of `MatchResult`**, each carrying the score,
the human-readable `reasons`, and the `feature_breakdown` — the *explanation* is the product.
`k` is clamped to 1–50.

#### `POST /match/jobs` → `200` *(auth optional)*

Hiree flow — resume text in, best-fit jobs out:
```json
{ "resume_text": "Backend engineer, 6y Python...", "k": 5, "sources": ["sample"] }
```
- `resume_text` — required, min length 1.
- `sources` — `null`/omitted = all available sources.

#### `POST /match/jobs/upload` → `200` *(auth optional)*

Same as above but from an uploaded file (`multipart/form-data`):
- `file` — a `.txt`, `.md`, `.pdf`, or `.docx` resume.
- `k` — form field, default 10.
- `sources` — form field, **comma-separated** string (e.g. `sample,demo`).

A file that yields no extractable text → `400`. (`.pdf`/`.docx` need the optional parser deps from
`requirements-optional.txt`; without them those formats fail gracefully to empty text → `400`.)

#### `POST /match/candidates` → `200` *(auth optional)*

Hirer flow — a job in, best-fit candidates out. Identify the job **either** by id (from the enabled
sources) **or** by pasted text:
```json
{ "job_id": "j-002", "k": 5, "sources": ["sample"] }
```
```json
{ "job_text": "Hiring an ML engineer skilled in Python, PyTorch, NLP",
  "job_title": "Machine Learning Engineer", "k": 3, "sources": ["sample"] }
```
- Neither `job_id` nor `job_text` provided → `400`.
- `job_id` given but not found in the sources → `404`.
- `job_title` is optional but improves role-matching when pasting free text.

#### `GET /match/history` → `200` *(auth required)*

The signed-in user's saved runs, newest first. Each row:
```json
{
  "id": 12,
  "direction": "jobs",              // "jobs" (hiree) or "candidates" (hirer)
  "query_summary": "Resume match -> 5 jobs",
  "result_count": 5,
  "created_at": "2026-07-07T20:00:00+00:00",
  "results": [ /* full ranked MatchResult[] */ ]
}
```
No/invalid token → `401`.

---

## Data model (persistence)

Two tables, both created automatically (`mindbridge/web/models.py`):

- **`users`** — `id`, unique `email`, bcrypt `hashed_password`, `role`, `created_at`.
- **`match_history`** — `user_id`, `direction`, `query_summary`, `result_count`, `results_json`
  (the full ranked `MatchResult[]` serialized as JSON text), `created_at`.

`match_history` is also the seed of the outcome-label data **M5** will learn from: a `hired` /
`satisfaction` column drops in here later with no other schema change.

## Error conventions

Standard FastAPI JSON errors, `{ "detail": "..." }`:

| Status | When |
|--------|------|
| `400`  | Missing required matching input; unreadable upload |
| `401`  | Missing/invalid/expired token on a protected route; bad login |
| `404`  | `job_id` not found |
| `409`  | Registering an already-used email |
| `422`  | Request body fails validation (Pydantic) |

## Configuration reference

All settings come from `mindbridge/config.py` (`.env` supported; some vars use a `MINDBRIDGE_`
prefix wired up manually — see the note in that file). Web-relevant ones:

| Setting / env var | Default | Purpose |
|-------------------|---------|---------|
| `MINDBRIDGE_SECRET_KEY` | placeholder | JWT signing secret — **override in prod** |
| `access_token_expire_minutes` | `1440` (24h) | Token lifetime |
| `database_url` | `sqlite:///data/mindbridge.db` | Persistence store |
| `cors_origins` | `localhost:5173`, `127.0.0.1:5173` | Allowed browser origins (Vite dev default, ready for the M3 React app) |
| `MINDBRIDGE_CORPUS_LIMIT` | none | Cap jobs/candidates per source for fast startup |

## Design notes

- **The web layer is a thin wrapper.** Routers validate and delegate to `web/services.py`; the
  engine stays importable and web-agnostic (an M1 design rule so M2 could wrap it without a
  refactor).
- **DTOs are separate from engine schemas.** `web/dto.py` holds request models; responses reuse the
  engine's `JobPosting` / `MatchResult` verbatim, since those are already the shape a UI wants.
- **One engine per process.** `services.get_engine()` lazily builds a singleton `MatchEngine`,
  caching the process-wide embedder + reranker choice.
- **Graceful degradation carries over.** No torch → TF-IDF embedder; no trained artifact →
  heuristic reranker; a dead source contributes nothing rather than failing the request.
