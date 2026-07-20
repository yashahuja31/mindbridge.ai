/**
 * Renders one ranked `MatchResult`: rank, matched title/company, salary & location badges,
 * direct "Apply on Spot" CTA link, expandable full description, score meter, reasons, and breakdown.
 */

import { useState } from 'react'
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  MapPin,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { FeatureBar, ScoreMeter } from '@/components/ScoreMeter'
import type { MatchResult } from '@/types'

const FEATURE_LABELS: Record<string, string> = {
  skill_coverage: 'Skill coverage',
  skill_overlap: 'Skill overlap',
  experience_match: 'Experience',
  location_match: 'Location',
  salary_fit: 'Salary',
  role_match: 'Role',
  semantic: 'Semantic',
}

function humanize(key: string): string {
  return (
    FEATURE_LABELS[key] ??
    key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  )
}

function formatSalary(min?: number | null, max?: number | null): string | null {
  if (!min && !max) return null
  const fmt = (n: number) =>
    n >= 1000 ? `$${Math.round(n / 1000)}k` : `$${n}`
  if (min && max) return `${fmt(min)} - ${fmt(max)}/yr`
  if (min) return `From ${fmt(min)}/yr`
  if (max) return `Up to ${fmt(max)}/yr`
  return null
}

export function MatchResultCard({ result, rank }: { result: MatchResult; rank: number }) {
  const [showDesc, setShowDesc] = useState(false)
  const features = Object.entries(result.feature_breakdown)
  const salaryStr = formatSalary(result.salary_min, result.salary_max)

  const applyTargetUrl =
    result.apply_url ||
    `https://www.google.com/search?q=${encodeURIComponent(`apply ${result.matched_label || result.matched_id}`)}`

  return (
    <Card className="overflow-hidden transition-all duration-200 hover:border-primary/40 hover:shadow-md">
      <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground">
              {rank}
            </span>
            <h3 className="text-lg font-semibold leading-tight text-foreground">
              {result.matched_label || result.matched_id}
            </h3>
          </div>

          {/* Location / Remote / Salary badges */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            {result.company && (
              <span className="inline-flex items-center gap-1 font-medium text-foreground">
                <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                {result.company}
              </span>
            )}
            {result.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                {result.location}
              </span>
            )}
            {result.remote && (
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

        {/* Action Button & Score Meter */}
        <div className="flex flex-col items-end gap-3 sm:shrink-0">
          <ScoreMeter score={result.score} />
          <Button
            asChild
            size="sm"
            className="gap-1.5 font-medium shadow-sm"
          >
            <a href={applyTargetUrl} target="_blank" rel="noopener noreferrer">
              Apply on Spot
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* Reasons */}
        {result.reasons.length > 0 && (
          <ul className="space-y-1.5 rounded-lg bg-muted/40 p-3">
            {result.reasons.map((reason, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        )}

        {/* Expandable Description */}
        {result.description && (
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
                {result.description}
              </div>
            )}
          </div>
        )}

        {/* Score breakdown */}
        {features.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Match breakdown
            </p>
            <div className="grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2">
              {features.map(([key, value]) => (
                <FeatureBar key={key} label={humanize(key)} value={value} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
