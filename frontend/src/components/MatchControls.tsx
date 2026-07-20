/**
 * Shared building blocks for pages that run a match and render ranked results: the k/sources
 * controls, the results list, and the `useMatchRunner` hook (loading + toasts). Used by the
 * ad-hoc Match page and the saved Profile page so both flows look and behave identically.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import { Sparkles } from 'lucide-react'

import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { MatchResultCard } from '@/components/MatchResultCard'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { MatchResult } from '@/types'

export const SOURCES: { id: string; label: string; hint: string }[] = [
  { id: 'sample', label: 'Sample Jobs', hint: 'real tech roles' },
  { id: 'real', label: 'Live Real Jobs', hint: 'live remote API' },
  { id: 'api', label: 'Adzuna API', hint: 'global jobs' },
  { id: 'demo', label: 'Demo corpus', hint: '10k · slower' },
]

/** Runs a match request, tracks loading/results, and toasts errors (and the history save). */
export function useMatchRunner() {
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

export function ControlsRow(props: {
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

export function Results({
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
