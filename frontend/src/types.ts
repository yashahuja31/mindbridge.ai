/**
 * TypeScript mirrors of the backend contract (see `docs/API.md` and `mindbridge/web/dto.py` +
 * `mindbridge/schemas.py`). Responses reuse the engine's `JobPosting` / `MatchResult` verbatim,
 * so these shapes track the Pydantic models one-to-one.
 */

export type Role = 'hiree' | 'hirer'

export interface User {
  id: number
  email: string
  role: Role
  created_at: string
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
