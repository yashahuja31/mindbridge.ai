# Frontend guide

The MindBridge web app is a **React 18 + TypeScript SPA** in [`frontend/`](../frontend/), built
with Vite, styled with Tailwind CSS (+ a small set of shadcn-style primitives), routed with
React Router. It consumes only the public HTTP API ([API.md](API.md)).

## Run it

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173  (backend must be running on :8000)
```

Other scripts: `npm run build` (typecheck + production bundle → `dist/`),
`npm run typecheck`, `npm run preview` (serve the built bundle locally).

## How it talks to the backend

In dev, all requests go to `/api/*` and **Vite proxies them** to `http://127.0.0.1:8000`
(`vite.config.ts`), so everything is same-origin — no CORS in play, no hardcoded host.

For a production build, set the target API once:

```bash
VITE_API_BASE=https://api.example.com npm run build
```

(`src/lib/api.ts` reads `import.meta.env.VITE_API_BASE`, defaulting to `/api`.)

## Structure

```
src/
  main.tsx               entry: router + AuthProvider + toaster; applies saved theme pre-paint
  App.tsx                routes; RequireAuth gate for /profile and /history
  types.ts               TS mirrors of the backend contract (keep in lockstep with dto.py/schemas.py)
  lib/api.ts             the one typed API client — every fetch in the app goes through it
  context/AuthContext.tsx JWT in localStorage, validated against /auth/me; login/register/
                          loginWithToken(OAuth)/logout
  pages/
    MatchPage.tsx        home: both matching flows, works signed-out; health badge
    AuthPage.tsx         sign in / register + OAuth buttons; consumes /login#token=… fragment
    ProfilePage.tsx      hiree: saved profile · hirer: postings CRUD — each with one-click match
    HistoryPage.tsx      saved runs, expandable to full ranked results
  components/
    Layout.tsx           header/nav/theme toggle/auth state
    MatchResultCard.tsx  one ranked result: score meter, reasons, feature breakdown
    MatchControls.tsx    shared k-slider + source pills + results list + runner hook
    ScoreMeter.tsx       0–1 score → labelled meter
    ui/                  button, card, input, tabs, … (shadcn-style primitives)
```

## Conventions

- **One API client.** No raw `fetch` in components — add a function to `src/lib/api.ts` and a
  type to `src/types.ts`. `ApiError` carries the HTTP status + the server's `detail`, which
  pages surface via toasts.
- **Types mirror the backend.** If you change `dto.py` or `schemas.py`, update `types.ts` in
  the same change (the file header says exactly what it mirrors).
- **Auth is a context, not a prop.** `useAuth()` gives `{ user, token, login, register,
  loginWithToken, logout }`. Matching works signed-out; a present token additionally saves
  history — pages don't branch on auth beyond that.
- **OAuth is a redirect, not a fetch.** The buttons navigate to
  `/api/auth/oauth/{provider}/start`; the backend eventually lands the browser on
  `/login#token=…`, which `AuthPage` consumes once, validates, stores, and scrubs from the URL.
  Buttons render only for providers the backend reports in `GET /auth/providers`.
- **Theme** is a `dark` class on `<html>`, persisted in localStorage, applied before first
  paint (in `main.tsx`) to avoid a flash.

## Deploying

The SPA is static files. `npm run build` → serve `frontend/dist/` from any static host
(Netlify, Vercel, nginx, or the API host itself). Three production knobs:

1. `VITE_API_BASE` at build time → the deployed API's URL.
2. Backend `cors_origins` (config.py) → include the SPA's origin.
3. Backend `FRONTEND_URL` → the SPA's origin, so OAuth callbacks land in the right place
   (see [AUTH.md](AUTH.md)).

Use a host rewrite so unknown paths serve `index.html` (client-side routing).
