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

Auth is **optional for matching** and **required for history/profiles/postings**. It uses JWT
bearer tokens (HS256), signed with `settings.secret_key`. There are two ways to obtain a token —
password or OAuth — and everything downstream treats them identically.

**Password:**
1. `POST /auth/register` or `POST /auth/login` returns `{ "access_token": "...", "token_type": "bearer" }`.
2. Send it on subsequent requests as `Authorization: Bearer <token>`.

**OAuth (Google / GitHub)** — browser-driven; see [`AUTH.md`](AUTH.md) for setup:
1. `GET /auth/providers` lists the configured providers (no keys configured = empty list).
2. Navigate the browser to `GET /auth/oauth/{provider}/start?role=hiree|hirer`.
3. After consent, the backend redirects to `<FRONTEND_URL>/login#token=<jwt>` (or `#error=<message>`).

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
(`username` is the email.) Bad credentials → `401`. An account created via OAuth has no local
password — attempting password login for it → `400` with a "use the Google/GitHub button" message.
Returns a `Token`.

#### `GET /auth/me` → `200` *(auth required)*

Returns the current user `{ id, email, role, auth_provider, created_at }`. Missing/invalid token
→ `401`. Handy as a token-validity probe. `auth_provider` is `"password"`, `"google"`, or
`"github"` — how the account was created.

#### `GET /auth/providers` → `200`

Which OAuth providers are configured, e.g. `[{ "name": "google" }, { "name": "github" }]`. A
provider appears **iff** both its client id and secret are set in the environment — an empty
list means password auth only, and the SPA renders no OAuth buttons.

#### `GET /auth/oauth/{provider}/start` → `307`

Begins the OAuth flow: redirects the browser to the provider's consent screen. Query param
`role` (`hiree` default, or `hirer`) is applied **only** if this sign-in creates a new account;
it rides inside the signed `state` token. Unknown/unconfigured provider → `404`.

#### `GET /auth/oauth/{provider}/callback` → `307`

The provider redirects here after consent; **clients never call this directly.** On success the
browser is redirected to `<FRONTEND_URL>/login#token=<jwt>`; on any failure (cancelled consent,
invalid `state`, failed code exchange, no verified email) to `<FRONTEND_URL>/login#error=<message>`.
Account linking is by verified email: an existing account with the same email simply signs in;
otherwise a new account is created with `auth_provider` set to the provider name.

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

### Profile (hiree) *(all auth required)*

A signed-in hiree keeps **one** persistent matching profile, so matching becomes one click — no
re-pasting a resume. Skills and experience are auto-extracted from `resume_text` when omitted.

#### `GET /profile` → `200`

The saved profile, or `404` until one exists (the 404 is the "empty state", not an error).

#### `PUT /profile` → `200`

Create/update (idempotent upsert). All fields optional-ish — a bare `resume_text` is enough:
```json
{
  "name": "Ada Lovelace",
  "headline": "Senior Backend Engineer",
  "skills": null,                    // null/omitted = auto-extract from resume_text
  "years_experience": null,          // null/omitted = auto-extract
  "location": "Mumbai",
  "open_to_remote": true,
  "desired_salary": 90000,
  "resume_text": "Backend engineer, 6y Python..."
}
```
Returns the stored `Profile` (with resolved `skills`, `years_experience`, `updated_at`).

#### `DELETE /profile` → `204`

#### `POST /profile/match` → `200`

Run the hiree flow from the saved profile: `{ "k": 5, "sources": ["sample"] }`. The run is saved
to history. An empty profile (no resume/headline/skills) → `400`.

### Postings (hirer) *(all auth required)*

A signed-in hirer keeps **many** saved job postings and can match candidates against any of them
in one click. Skills are auto-extracted from `title` + `description` when omitted.

#### `GET /postings` → `200` — the user's postings, newest first.

#### `POST /postings` → `201`

```json
{
  "title": "Machine Learning Engineer",
  "company": "Acme Corp",
  "description": "What the role involves...",
  "skills": null,                    // null/omitted = auto-extract
  "min_experience": 0, "max_experience": null,
  "location": "Bengaluru", "remote": true,
  "salary_min": null, "salary_max": null
}
```
`title` is the only required field.

#### `GET /postings/{id}` → `200` · `PUT /postings/{id}` → `200` · `DELETE /postings/{id}` → `204`

Postings are owned: another user's posting id → `404`.

#### `POST /postings/{id}/match` → `200`

Run the hirer flow from the saved posting: `{ "k": 5, "sources": ["sample"] }`. Saved to history.

---

## Data model (persistence)

Four tables, all created automatically (`mindbridge/web/models.py`):

- **`users`** — `id`, unique `email`, bcrypt `hashed_password` (NULL for OAuth-created
  accounts), `auth_provider` (`password`/`google`/`github`), `role`, `created_at`.
- **`match_history`** — `user_id`, `direction`, `query_summary`, `result_count`, `results_json`
  (the full ranked `MatchResult[]` serialized as JSON text), `created_at`.
- **`profiles`** — one row per hiree (`user_id` unique): resume text + structured fields
  (`skills_json`, `years_experience`, `location`, `open_to_remote`, `desired_salary`), `updated_at`.
- **`postings`** — many rows per hirer: a saved `JobPosting`-shaped role (`skills_json`,
  experience/salary bounds, `location`, `remote`), `created_at`/`updated_at`.

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
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | empty | Enable "Continue with Google" (see AUTH.md) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | empty | Enable "Continue with GitHub" (see AUTH.md) |
| `FRONTEND_URL` | `http://localhost:5173` | Where OAuth callbacks land the browser |
| `API_BASE_URL` | `http://127.0.0.1:8000` | Public base URL used to build OAuth redirect URIs |

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
