/** The signed-in user's saved runs, newest first. Each row expands to its full ranked results. */

import { useEffect, useState } from 'react'
import { ChevronDown, History, Loader2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { MatchResultCard } from '@/components/MatchResultCard'
import { useAuth } from '@/context/AuthContext'
import * as api from '@/lib/api'
import { ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { HistoryRow } from '@/types'

function formatWhen(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

export function HistoryPage() {
  const { token } = useAuth()
  const [rows, setRows] = useState<HistoryRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openId, setOpenId] = useState<number | null>(null)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    api
      .getHistory(token)
      .then((r) => {
        if (!cancelled) setRows(r)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load history')
      })
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <History className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold tracking-tight">Match history</h1>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {!rows && !error && (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading…
        </div>
      )}

      {rows && rows.length === 0 && (
        <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">
          No saved runs yet. Run a match from the{' '}
          <span className="font-medium text-foreground">Match</span> page and it'll show up here.
        </div>
      )}

      {rows && rows.length > 0 && (
        <div className="space-y-3">
          {rows.map((row) => {
            const open = openId === row.id
            return (
              <Card key={row.id}>
                <button
                  type="button"
                  className="w-full text-left"
                  onClick={() => setOpenId(open ? null : row.id)}
                  aria-expanded={open}
                >
                  <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
                    <div className="min-w-0 space-y-1">
                      <CardTitle className="truncate text-base">{row.query_summary}</CardTitle>
                      <p className="text-xs text-muted-foreground">{formatWhen(row.created_at)}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="secondary">
                        {row.direction === 'jobs' ? 'Jobs' : 'Candidates'}
                      </Badge>
                      <Badge variant="muted">{row.result_count}</Badge>
                      <ChevronDown
                        className={cn(
                          'h-4 w-4 text-muted-foreground transition-transform',
                          open && 'rotate-180',
                        )}
                      />
                    </div>
                  </CardHeader>
                </button>
                {open && (
                  <CardContent className="space-y-4 border-t pt-4">
                    {row.results.map((r, i) => (
                      <MatchResultCard key={`${r.matched_id}-${i}`} result={r} rank={i + 1} />
                    ))}
                  </CardContent>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
