/**
 * TypeScript mirrors of the backend contract (see `docs/API.md` and `mindbridge/web/dto.py` +
 * `mindbridge/schemas.py`). Responses reuse the engine's `JobPosting` / `MatchResult` verbatim,
 * so these shapes track the Pydantic models one-to-one.
 */

export type Role = 'hiree' | 'hirer'

/** How the account was created; OAuth accounts have no local password. */
export type AuthProvider = 'password' | 'google' | 'github'

export interface User {
  id: number
  email: string
  role: Role
  auth_provider: AuthProvider
  created_at: string
}

/** One configured OAuth provider from `GET /auth/providers` — render a button per entry. */
export interface OAuthProviderInfo {
  name: string
}

export interface Token {
  access_token: string
  token_type: string
}

/** An open role, normalized from whatever source produced it. */
export interface JobPosting {
  id: string
  title: string
  company: string
  description: string
  skills: string[]
  preferred_skills: string[]
  min_experience: number
  max_experience: number | null
  location: string
  remote: boolean
  salary_min: number | null
  salary_max: number | null
  source: string
  apply_url?: string | null
  raw_text: string
}

/**
 * One ranked pairing. Direction-agnostic: `subject_id` is who we matched *for*, `matched_id` is
 * the thing recommended to them. The explanation (`reasons` + `feature_breakdown`) is the product.
 */
export interface MatchResult {
  subject_id: string
  matched_id: string
  matched_label: string
  score: number
  semantic_score: number
  rerank_score: number
  reasons: string[]
  feature_breakdown: Record<string, number>
  apply_url?: string | null
  company?: string | null
  location?: string | null
  description?: string | null
  salary_min?: number | null
  salary_max?: number | null
  remote?: boolean | null
  skills?: string[]
}

export type MatchDirection = 'jobs' | 'candidates'

/** A saved run from `GET /match/history`, including its full ranked results. */
export interface HistoryRow {
  id: number
  direction: MatchDirection
  query_summary: string
  result_count: number
  created_at: string
  results: MatchResult[]
}

export interface HealthInfo {
  status: string
  embedder: string
  reranker: string
}

// ---- Persistent profiles & postings (M3) ---------------------------------------------------

/** A hiree's saved matching profile (`GET/PUT /profile`). */
export interface Profile {
  name: string
  headline: string
  skills: string[]
  years_experience: number
  location: string
  open_to_remote: boolean
  desired_salary: number | null
  resume_text: string
  updated_at: string
}

/** Payload for `PUT /profile`. `skills`/`years_experience` omitted → auto-extracted server-side. */
export interface ProfileIn {
  name?: string
  headline?: string
  skills?: string[] | null
  years_experience?: number | null
  location?: string
  open_to_remote?: boolean
  desired_salary?: number | null
  resume_text?: string
}

/** A hirer's saved job posting (`/postings`). */
export interface Posting {
  id: number
  title: string
  company: string
  description: string
  skills: string[]
  min_experience: number
  max_experience: number | null
  location: string
  remote: boolean
  salary_min: number | null
  salary_max: number | null
  apply_url?: string | null
  created_at: string
  updated_at: string
}

/** Payload for `POST/PUT /postings`. `skills` omitted → auto-extracted from title+description. */
export interface PostingIn {
  title: string
  company?: string
  description?: string
  skills?: string[] | null
  min_experience?: number
  max_experience?: number | null
  location?: string
  remote?: boolean
  salary_min?: number | null
  salary_max?: number | null
  apply_url?: string | null
}
