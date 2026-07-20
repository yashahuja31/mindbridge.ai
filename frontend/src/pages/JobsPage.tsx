/**
 * Explore Real Jobs page: direct job search & live job board with direct "Apply on Spot" links.
 * Pulls real job postings from active sources (`real`, `sample`, `api`) via `GET /jobs`.
 */

import { useEffect, useState } from 'react'
import {
  Building2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Loader2,
  MapPin,
  Search,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import * as api from '@/lib/api'
import { cn } from '@/lib/utils'
import type { JobPosting } from '@/types'

function formatSalary(min?: number | null, max?: number | null): string | null {
  if (!min && !max) return null
  const fmt = (n: number) => (n >= 1000 ? `$${Math.round(n / 1000)}k` : `$${n}`)
  if (min && max) return `${fmt(min)} - ${fmt(max)}/yr`
  if (min) return `From ${fmt(min)}/yr`
  if (max) return `Up to ${fmt(max)}/yr`
  return null
}

function JobCard({ job }: { job: JobPosting }) {
  const [showDesc, setShowDesc] = useState(false)
  const salaryStr = formatSalary(job.salary_min, job.salary_max)
  const applyTargetUrl =
    job.apply_url ||
    `https://www.google.com/search?q=${encodeURIComponent(`apply ${job.title} ${job.company} jobs`)}`

  return (
    <Card className="overflow-hidden transition-all duration-200 hover:border-primary/40 hover:shadow-md">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold leading-tight text-foreground">
              {job.title}
            </h3>
            <Badge variant="outline" className="text-[11px] capitalize">
              {job.source}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {job.company && (
              <span className="inline-flex items-center gap-1 font-medium text-foreground">
                <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                {job.company}
              </span>
            )}
            {job.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                {job.location}
              </span>
            )}
            {job.remote && (
              <Badge variant="secondary" className="px-2 py-0.5 text-[11px] font-normal">
                Remote
              </Badge>
            )}
            {salaryStr && (
              <Badge variant="outline" className="px-2 py-0.5 text-[11px] font-semibold text-primary">
                {salaryStr}
              </Badge>
            )}
          </div>
        </div>

        <Button asChild size="sm" className="gap-1.5 font-medium shadow-sm sm:shrink-0">
          <a href={applyTargetUrl} target="_blank" rel="noopener noreferrer">
            Apply on Spot
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </Button>
      </CardHeader>

      <CardContent className="space-y-4">
        {job.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {job.skills.map((skill) => (
              <Badge key={skill} variant="muted" className="text-xs">
                {skill}
              </Badge>
            ))}
          </div>
        )}

        {job.description && (
          <div className="border-t border-border/50 pt-3">
            <button
              type="button"
              onClick={() => setShowDesc(!showDesc)}
              className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary hover:underline"
            >
              {showDesc ? (
                <>
                  Hide Description <ChevronUp className="h-3.5 w-3.5" />
                </>
              ) : (
                <>
                  View Job Description <ChevronDown className="h-3.5 w-3.5" />
                </>
              )}
            </button>
            {showDesc && (
              <div className="mt-2.5 max-h-60 overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
                {job.description}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function JobsPage() {
  const [jobs, setJobs] = useState<JobPosting[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [source, setSource] = useState<string>('all')

  useEffect(() => {
    let active = true
    setLoading(true)
    const sources = source === 'all' ? ['sample', 'real', 'api'] : [source]
    api
      .listJobs({ q: query, limit: 50, sources })
      .then((data) => {
        if (active) {
          setJobs(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [query, source])

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <section className="space-y-3 text-center">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Explore Real Job Opportunities
        </h1>
        <p className="mx-auto max-w-xl text-muted-foreground">
          Browse top software, AI, engineering, product, and data roles from top tech companies and live APIs — with direct application links to apply on the spot.
        </p>
      </section>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search roles by keyword or tech (e.g. Python, React, AI, Stripe)..."
            className="pl-9"
          />
        </div>

        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">Source:</Label>
          <div className="flex gap-1.5">
            {[
              { id: 'all', label: 'All Jobs' },
              { id: 'real', label: 'Live Real Jobs' },
              { id: 'sample', label: 'Top Companies' },
            ].map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSource(s.id)}
                className={cn(
                  'rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
                  source === s.id
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-input bg-background text-muted-foreground hover:bg-muted',
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Fetching real job opportunities…
        </div>
      ) : jobs.length === 0 ? (
        <div className="rounded-xl border border-dashed p-12 text-center text-muted-foreground">
          No job postings found matching "{query}". Try a different keyword or source filter.
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Showing {jobs.length} active job opportunities
          </p>
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </div>
  )
}
