# Authentication

MindBridge has **two ways in and one token out**. Whether you sign in with a password or with
Google/GitHub, the backend ends the flow by minting the same HS256 JWT — so every downstream
endpoint (`/auth/me`, history, profiles, postings) is auth-method-agnostic.

```
password ─► POST /auth/login ───────────────┐
                                            ├─► HS256 JWT ─► Authorization: Bearer <token>
Google/GitHub ─► /auth/oauth/{p}/start ─────┘
                 └► provider consent ─► /auth/oauth/{p}/callback ─► SPA /login#token=...
```

- Tokens are signed with `MINDBRIDGE_SECRET_KEY` and expire after 24 h (configurable).
- Matching endpoints work **without** a token; a valid token additionally saves runs to history.
- Passwords are bcrypt-hashed. OAuth accounts have **no** local password (`hashed_password` is
  NULL) and password login for them returns a clear "use the Google/GitHub button" error.

## Email + password (zero config)

Works out of the box:

1. `POST /auth/register` `{ "email", "password", "role": "hiree" | "hirer" }` → `201` + token.
2. `POST /auth/login` — OAuth2 password grant, **form-encoded**, `username` = email → token.
3. Send `Authorization: Bearer <token>` on subsequent requests.

## OAuth (Google / GitHub)

### How it's wired

The classic **authorization-code flow**, implemented in `mindbridge/web/oauth.py` (providers) and
`mindbridge/web/routers/auth.py` (routes):

1. The SPA calls `GET /auth/providers` and renders one "Continue with …" button per configured
   provider. **A provider is configured ⇔ both its client id and secret are set.** No keys → no
   buttons → no attack surface.
2. Clicking a button navigates (full page, not fetch) to `GET /auth/oauth/{provider}/start?role=…`.
   The backend redirects to the provider's consent screen, carrying a `state` parameter — a
   **short-lived signed JWT** (10 min, purpose-tagged so it can never be replayed as an access
   token). That keeps the API stateless: no server-side session storage to verify the round-trip.
3. The provider redirects back to `GET /auth/oauth/{provider}/callback?code=…&state=…`. The
   backend verifies `state`, exchanges the `code` for a provider access token, and fetches the
   user's **verified email** (Google userinfo; GitHub `/user/emails`, primary-verified first).
4. Find-or-create by email: an existing password account simply logs in (same person, same
   inbox — it keeps its password); a new account is created with `auth_provider = "google" |
   "github"` and the role picked before the redirect.
5. The browser is sent back to the SPA at `/login#token=…`. The token rides in the URL
   **fragment**, which is never sent to servers — it can't leak into access logs or referrers.
   The SPA consumes it, validates it against `/auth/me`, stores it, and scrubs the URL.

Every failure (cancelled consent, forged/expired state, failed code exchange, no verified email)
lands the user back on `/login#error=<readable message>` instead of a bare JSON error page.

### Setting up Google

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) → create/select a project.
2. **APIs & Services → OAuth consent screen**: External, app name, your email. Scopes: only
   `openid` and `email` are needed (the code requests exactly `openid email`).
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - Authorized redirect URI: `http://127.0.0.1:8000/auth/oauth/google/callback`
     (in production: `https://<your-api-host>/auth/oauth/google/callback`)
4. Copy the client id + secret into `.env`:

```dotenv
GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
```

5. Restart the API. `GET /auth/providers` now lists `google` and the SPA shows the button.

### Setting up GitHub

1. GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Fill in:
   - Homepage URL: `http://localhost:5173` (or your deployed frontend)
   - Authorization callback URL: `http://127.0.0.1:8000/auth/oauth/github/callback`
3. Register, then **Generate a new client secret**, and set:

```dotenv
GITHUB_CLIENT_ID=Iv1....
GITHUB_CLIENT_SECRET=...
```

4. Restart the API. Done.

> GitHub note: the app requests `read:user user:email` so it can read the verified email even
> when the profile email is private. Users with **no verified email** on GitHub are rejected
> with a readable error (an unverified address could hijack an existing account).

### Deployment URLs

Two settings tell the backend where things live (defaults suit local dev):

```dotenv
API_BASE_URL=http://127.0.0.1:8000    # used to build the redirect_uri sent to providers
FRONTEND_URL=http://localhost:5173    # where callbacks land the browser (SPA /login page)
```

When deploying, set both to their public URLs **and** register the new callback URL with each
provider. The `redirect_uri` sent must match the registered one exactly — that's the most common
OAuth setup error.

### Adding another provider

`mindbridge/web/oauth.py` mirrors the ingestion-registry pattern: a provider is one
`OAuthProvider` entry in the `PROVIDERS` dict — authorize/token URLs, scope, two settings
getters, and a `fetch_email` function. Add the entry plus two config fields and you're done; the
routes, discovery endpoint, and SPA buttons all key off the dict.

## Why not Clerk (or Auth0/Firebase)?

Considered and deliberately not used — for this project, at this stage:

- **Offline-first is a design rule here.** The whole stack — engine, API, UI, tests — runs with
  no network and no keys. A hosted auth provider would make sign-in (and any test touching it)
  depend on a third-party service and dashboard config.
- **The need is small.** Email lookup + JWT is the entire requirement; sessions, orgs, MFA, and
  user-management UI (where Clerk shines) aren't in scope yet.
- **The data stays in one place.** Users live in the same SQLite/Postgres database as profiles
  and match history — one backup, one migration story, and the M5 learning loop can join on
  `user_id` freely.

**If you want Clerk later** (it's a good choice once real users, MFA, or social-account
management arrive), the seam is already clean:

1. Frontend: wrap the app in `<ClerkProvider>`, replace `AuthPage` with Clerk's `<SignIn />`,
   and send Clerk's session JWT as the bearer token.
2. Backend: replace `security.get_current_user`'s decode step with verification of Clerk's JWT
   (their JWKS endpoint), mapping `sub` → a `users` row keyed by Clerk user id.
3. Delete nothing else — routers, services, and models only ever see a `User` row.

The same recipe applies to Auth0 or any OIDC issuer: only `security.py` (verify) and the login
UI change; the `User` table and every route stay as they are.

## Threat-model notes (what's covered, what's not)

Covered: bcrypt (72-byte truncation handled), purpose-tagged state JWTs (CSRF on the OAuth
round-trip), verified-email-only account linking, token-in-fragment (no server logs), OAuth
accounts immune to password guessing (no password), providers dark unless configured.

Not yet (fine for a demo, needed for production): rate limiting on login/register, refresh
tokens / revocation (tokens live 24 h and can't be revoked), email verification for password
sign-ups, PKCE (server-side confidential client uses client_secret instead), account-level
audit log.
