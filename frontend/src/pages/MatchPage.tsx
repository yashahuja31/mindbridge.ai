/**
 * The product's core, both directions:
 *   - Hiree ("Find jobs"): paste or upload a resume → best-fit jobs.
 *   - Hirer ("Find candidates"): a job (pasted JD, optional title, or an id) → best-fit candidates.
 *
 * Matching runs anonymously; when signed in, each run is also saved to the user's history (the
 * backend does this automatically when a token is present).
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { FileUp, Loader2, Search, Sparkles, UserRound, Users } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { MatchResultCard } from '@/components/MatchResultCard'
import { useAuth } from '@/context/AuthContext'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { HealthInfo, MatchResult } from '@/types'

const SOURCES: { id: string; label: string; hint: string }[] = [
  { id: 'sample', label: 'Sample', hint: 'fast · offline' },
  { id: 'demo', label: 'Demo corpus', hint: '10k · slower' },
]

export function MatchPage() {
  const { user, token } = useAuth()
  // Default the active tab to the signed-in user's role.
  const [tab, setTab] = useState<'jobs' | 'candidates'>(user?.role === 'hirer' ? 'candidates' : 'jobs')

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <section className="space-y-3 text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Matching on fit, not just keywords
        </h1>
        <p className="mx-auto max-w-xl text-muted-foreground">
          Two-sided job⇄talent matching with an <span className="text-foreground">explanation</span>{' '}
          for every result — the reasons and the score breakdown, not just a number.
        </p>
        {!user && (
          <p className="text-sm text-muted-foreground">
            <Link to="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>{' '}
            to save your match history.
          </p>
        )}
      </section>

      <Tabs value={tab} onValueChange={(v) => setTab(v as 'jobs' | 'candidates')}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="jobs">
            <UserRound className="h-4 w-4" />
            Find jobs
          </TabsTrigger>
          <TabsTrigger value="candidates">
            <Users className="h-4 w-4" />
            Find candidates
          </TabsTrigger>
        </TabsList>

        <TabsContent value="jobs">
          <HireeFlow token={token} />
        </TabsContent>
        <TabsContent value="candidates">
          <HirerFlow token={token} />
        </TabsContent>
      </Tabs>

      <HealthBadge />
    </div>
  )
}

// ---- Hiree: resume -> jobs ----------------------------------------------------------------

function HireeFlow({ token }: { token: string | null }) {
  const [resumeText, setResumeText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [k, setK] = useState(5)
  const [sources, setSources] = useState<string[]>(['sample'])
  const { results, running, run } = useMatchRunner()

  const canRun = file !== null || resumeText.trim().length > 0

  function onRun() {
    void run(() =>
      file
        ? api.matchJobsUpload(file, k, sources.length ? sources : null, token)
        : api.matchJobs(resumeText, k, sources.length ? sources : null, token),
    token != null,
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Your resume</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="resume">Paste resume text</Label>
            <Textarea
              id="resume"
              rows={7}
              placeholder="e.g. Backend engineer, 6y Python, FastAPI, PostgreSQL, Docker, AWS…"
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              disabled={file !== null}
            />
          </div>

          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs uppercase tracking-wide text-muted-foreground">or</span>
            <div className="h-px flex-1 bg-border" />
          </div>

          <FileField file={file} onFile={setFile} />

          <ControlsRow k={k} setK={setK} sources={sources} setSources={setSources} disabled={running} />

          <Button onClick={onRun} disabled={!canRun || running} className="w-full sm:w-auto">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Find matching jobs
          </Button>
        </CardContent>
      </Card>

      <Results results={results} noun="jobs" running={running} />
    </div>
  )
}

// ---- Hirer: job -> candidates -------------------------------------------------------------

function HirerFlow({ token }: { token: string | null }) {
  const [jobTitle, setJobTitle] = useState('')
  const [jobText, setJobText] = useState('')
  const [jobId, setJobId] = useState('')
  const [k, setK] = useState(5)
  const [sources, setSources] = useState<string[]>(['sample'])
  const { results, running, run } = useMatchRunner()

  const canRun = jobText.trim().length > 0 || jobId.trim().length > 0

  function onRun() {
    void run(
      () =>
        api.matchCandidates(
          {
            jobId: jobId.trim() || undefined,
            jobText: jobText.trim() || undefined,
            jobTitle: jobTitle.trim(),
            k,
            sources: sources.length ? sources : null,
          },
          token,
        ),
      token != null,
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">The role you're hiring for</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="job-title">Job title</Label>
            <Input
              id="job-title"
              placeholder="e.g. Machine Learning Engineer"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="job-text">Job description</Label>
            <Textarea
              id="job-text"
              rows={6}
              placeholder="Hiring an ML engineer skilled in Python, PyTorch, NLP…"
              value={jobText}
              onChange={(e) => setJobText(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="job-id">…or an existing job id</Label>
            <Input
              id="job-id"
              placeholder="e.g. j-002"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Provide a description above, or reference a job by id from the enabled sources.
            </p>
          </div>

          <ControlsRow k={k} setK={setK} sources={sources} setSources={setSources} disabled={running} />

          <Button onClick={onRun} disabled={!canRun || running} className="w-full sm:w-auto">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Find matching candidates
          </Button>
        </CardContent>
      </Card>

      <Results results={results} noun="candidates" running={running} />
    </div>
  )
}

// ---- Shared bits --------------------------------------------------------------------------

/** Runs a match request, tracks loading/results, and toasts errors (and the history save). */
function useMatchRunner() {
  const [results, setResults] = useState<MatchResult[] | null>(null)
  const [running, setRunning] = useState(false)

  async function run(fn: () => Promise<MatchResult[]>, saved: boolean) {
    setRunning(true)
    try {
      const res = await fn()
      setResults(res)
      if (res.length === 0) {
        toast.info('No matches found — try a different source or broaden your input.')
      } else if (saved) {
        toast.success(`${res.length} matches · saved to your history`)
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Matching failed'
      toast.error(msg)
    } finally {
      setRunning(false)
    }
  }

  return { results, running, run }
}

function FileField({ file, onFile }: { file: File | null; onFile: (f: File | null) => void }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor="resume-file">Upload a resume file</Label>
      <div className="flex items-center gap-3">
        <Button asChild variant="outline" size="sm">
          <label htmlFor="resume-file" className="cursor-pointer">
            <FileUp className="h-4 w-4" />
            Choose file
          </label>
        </Button>
        <input
          id="resume-file"
          type="file"
          accept=".txt,.md,.pdf,.docx"
          className="sr-only"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            {file.name}
            <button
              type="button"
              className="text-primary hover:underline"
              onClick={() => onFile(null)}
            >
              clear
            </button>
          </span>
        ) : (
          <span className="text-sm text-muted-foreground">.txt, .md, .pdf, or .docx</span>
        )}
      </div>
    </div>
  )
}

function ControlsRow(props: {
  k: number
  setK: (n: number) => void
  sources: string[]
  setSources: (s: string[]) => void
  disabled: boolean
}) {
  const { k, setK, sources, setSources, disabled } = props
  const toggle = (id: string) =>
    setSources(sources.includes(id) ? sources.filter((s) => s !== id) : [...sources, id])

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Results</Label>
          <span className="text-sm font-medium tabular-nums text-muted-foreground">{k}</span>
        </div>
        <Slider
          min={1}
          max={20}
          step={1}
          value={[k]}
          onValueChange={([v]) => setK(v)}
          disabled={disabled}
          aria-label="Number of results"
        />
      </div>

      <div className="space-y-2">
        <Label>Sources</Label>
        <div className="flex flex-wrap gap-2">
          {SOURCES.map((s) => {
            const active = sources.includes(s.id)
            return (
              <button
                key={s.id}
                type="button"
                disabled={disabled}
                onClick={() => toggle(s.id)}
                aria-pressed={active}
                className={cn(
                  'rounded-full border px-3 py-1 text-sm transition-colors disabled:opacity-50',
                  active
                    ? 'border-primary bg-accent text-accent-foreground'
                    : 'border-input text-muted-foreground hover:bg-muted',
                )}
              >
                {s.label}
                <span className="ml-1.5 text-xs opacity-70">{s.hint}</span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Results({
  results,
  noun,
  running,
}: {
  results: MatchResult[] | null
  noun: string
  running: boolean
}) {
  if (results === null) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
        <Sparkles className="mx-auto mb-2 h-6 w-6 opacity-60" />
        Your ranked {noun} will appear here.
      </div>
    )
  }
  if (results.length === 0 && !running) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
        No {noun} found. Try enabling another source or broadening your input.
      </div>
    )
  }
  return (
    <div className="space-y-4">
      <h2 className="text-sm font-medium text-muted-foreground">
        Top {results.length} {noun}, ranked by fit
      </h2>
      {results.map((r, i) => (
        <MatchResultCard key={`${r.matched_id}-${i}`} result={r} rank={i + 1} />
      ))}
    </div>
  )
}

/** Small connectivity/status pill — confirms the backend is reachable and which engine is active. */
function HealthBadge() {
  const [health, setHealth] = useState<HealthInfo | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .health()
      .then((h) => {
        if (!cancelled) setHealth(h)
      })
      .catch(() => {
        if (!cancelled) setOffline(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (offline) {
    return (
      <p className="text-center text-xs text-destructive">
        Backend unreachable — start it with <code>python -m mindbridge.cli serve</code>.
      </p>
    )
  }
  if (!health) return null
  return (
    <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-success" />
      API online
      <Badge variant="muted">embedder: {health.embedder}</Badge>
      <Badge variant="muted">reranker: {health.reranker}</Badge>
    </div>
  )
}
