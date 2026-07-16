# MindBridge.ai — Frontend (M3)

The React web app for the MindBridge matching engine: two-sided (hiree ⇄ hirer) matching with
explanations, auth, saved profiles/postings, and match history. Talks to the M2 FastAPI backend —
see `../docs/API.md` for the full HTTP contract.

## Stack

Vite · React 18 · TypeScript · Tailwind CSS · shadcn/ui (Radix) · React Router · sonner toasts ·
lucide-react icons. No axios — one small typed `fetch` client (`src/lib/api.ts`).

## Running it (two terminals)

```bash
# 1. backend, from the repo root (fast startup: cap the demo corpus)
MINDBRIDGE_CORPUS_LIMIT=200 python -m mindbridge.cli serve        # http://127.0.0.1:8000

# 2. frontend, from this directory
npm install
npm run dev                                                        # http://localhost:5173
```

In dev, API calls go to `/api/*` and Vite proxies them to `:8000` (see `vite.config.ts`) —
same-origin, no CORS setup needed. For a production build, set `VITE_API_BASE` to the deployed
backend URL and `npm run build` (output in `dist/`).

## Pages

| Route | What it does | Auth |
|-------|--------------|------|
| `/` | Ad-hoc matching — hiree (paste/upload resume → ranked jobs) and hirer (job id or pasted JD → ranked candidates) | optional¹ |
| `/profile` | Hiree: one saved profile + one-click match. Hirer: saved postings (CRUD) + one-click match per posting | required |
| `/history` | Saved runs, newest first, expandable to full results | required |
| `/login` | Sign in / create account (hiree or hirer) | — |

¹ Matching works anonymously; signing in additionally saves each run to history.

## Layout

```
src/
  lib/api.ts          typed API client (ApiError carries status + server detail)
  types.ts            TS mirrors of the backend contract (dto.py + schemas.py)
  context/AuthContext.tsx   token in localStorage, /auth/me revalidation on mount
  components/
    Layout.tsx        app shell: header, nav, theme toggle, auth state
    MatchControls.tsx shared k-slider/source-picker/results-list + useMatchRunner hook
    MatchResultCard.tsx / ScoreMeter.tsx   the explanation UI (reasons + feature bars)
  pages/              MatchPage, ProfilePage, HistoryPage, AuthPage
```

The design rule carried over from the engine: **the explanation is the product** — every result
renders its `reasons` and `feature_breakdown`, not just a score.
