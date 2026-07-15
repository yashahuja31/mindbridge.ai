/**
 * Typed client for the MindBridge M2 API.
 *
 * In dev, calls go to `/api/*` and Vite proxies them to the FastAPI server on :8000 (see
 * `vite.config.ts`), keeping everything same-origin. For a production build, point
 * `VITE_API_BASE` at the deployed backend.
 */

import type {
  HealthInfo,
  HistoryRow,
  JobPosting,
  MatchResult,
  Posting,
  PostingIn,
  Profile,
  ProfileIn,
  Role,
  Token,
  User,
} from '@/types'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

/** An error carrying the HTTP status and the server's `detail` message. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Pull a human-readable message out of FastAPI's `{ detail }` (string, or Pydantic 422 list). */
function detailToMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === 'string') return d
    if (Array.isArray(d) && d.length > 0) {
      const first = d[0] as { msg?: string } | undefined
      if (first?.msg) return first.msg
    }
  }
  return fallback
}

async function request<T>(
  path: string,
  opts: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = opts
  const h = new Headers(headers)
  if (token) h.set('Authorization', `Bearer ${token}`)

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...rest, headers: h })
  } catch {
    throw new ApiError(0, 'Cannot reach the API. Is the backend running (`mindbridge serve`)?')
  }

  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, detailToMessage(data, `Request failed (${res.status})`))
  }
  return data as T
}

// ---- Auth --------------------------------------------------------------------------------

export function register(email: string, password: string, role: Role): Promise<Token> {
  return request<Token>('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, role }),
  })
}

export function login(email: string, password: string): Promise<Token> {
  // OAuth2 password grant is form-encoded; `username` carries the email.
  const form = new URLSearchParams()
  form.set('username', email)
  form.set('password', password)
  return request<Token>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })
}

export function me(token: string): Promise<User> {
  return request<User>('/auth/me', { token })
}

// ---- Meta --------------------------------------------------------------------------------

export function health(): Promise<HealthInfo> {
  return request<HealthInfo>('/health')
}

// ---- Jobs --------------------------------------------------------------------------------

export function listJobs(
  params: { q?: string; limit?: number; sources?: string[] | null } = {},
): Promise<JobPosting[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.limit) qs.set('limit', String(params.limit))
  for (const s of params.sources ?? []) qs.append('sources', s)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request<JobPosting[]>(`/jobs${suffix}`)
}

// ---- Matching (auth optional; a token also persists the run to history) ------------------

export function matchJobs(
  resumeText: string,
  k: number,
  sources: string[] | null,
  token?: string | null,
): Promise<MatchResult[]> {
  return request<MatchResult[]>('/match/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resume_text: resumeText, k, sources }),
    token,
  })
}

export function matchJobsUpload(
  file: File,
  k: number,
  sources: string[] | null,
  token?: string | null,
): Promise<MatchResult[]> {
  const fd = new FormData()
  fd.set('file', file)
  fd.set('k', String(k))
  if (sources && sources.length > 0) fd.set('sources', sources.join(',')) // comma-separated
  return request<MatchResult[]>('/match/jobs/upload', { method: 'POST', body: fd, token })
}

export function matchCandidates(
  params: {
    jobId?: string
    jobText?: string
    jobTitle?: string
    k: number
    sources: string[] | null
  },
  token?: string | null,
): Promise<MatchResult[]> {
  return request<MatchResult[]>('/match/candidates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      job_id: params.jobId || null,
      job_text: params.jobText || null,
      job_title: params.jobTitle ?? '',
      k: params.k,
      sources: params.sources,
    }),
    token,
  })
}

export function getHistory(token: string): Promise<HistoryRow[]> {
  return request<HistoryRow[]>('/match/history', { token })
}

// ---- Profile (hiree; all routes require auth) ---------------------------------------------

export function getProfile(token: string): Promise<Profile> {
  return request<Profile>('/profile', { token })
}

export function putProfile(data: ProfileIn, token: string): Promise<Profile> {
  return request<Profile>('/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    token,
  })
}

export function deleteProfile(token: string): Promise<void> {
  return request<void>('/profile', { method: 'DELETE', token })
}

export function matchFromProfile(
  k: number,
  sources: string[] | null,
  token: string,
): Promise<MatchResult[]> {
  return request<MatchResult[]>('/profile/match', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ k, sources }),
    token,
  })
}

// ---- Postings (hirer; all routes require auth) --------------------------------------------

export function listPostings(token: string): Promise<Posting[]> {
  return request<Posting[]>('/postings', { token })
}

export function createPosting(data: PostingIn, token: string): Promise<Posting> {
  return request<Posting>('/postings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    token,
  })
}

export function updatePosting(id: number, data: PostingIn, token: string): Promise<Posting> {
  return request<Posting>(`/postings/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    token,
  })
}

export function deletePosting(id: number, token: string): Promise<void> {
  return request<void>(`/postings/${id}`, { method: 'DELETE', token })
}

export function matchFromPosting(
  id: number,
  k: number,
  sources: string[] | null,
  token: string,
): Promise<MatchResult[]> {
  return request<MatchResult[]>(`/postings/${id}/match`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ k, sources }),
    token,
  })
}
