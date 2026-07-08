/**
 * Renders one ranked `MatchResult`: rank, the matched label, the score meter, the human-readable
 * `reasons`, and the per-feature `feature_breakdown`. The explanation is the product, so reasons
 * and the breakdown are given as much room as the score.
 */

import { CheckCircle2 } from 'lucide-react'

import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { FeatureBar, ScoreMeter } from '@/components/ScoreMeter'
import type { MatchResult } from '@/types'

/** Friendly labels for the engine's feature keys (`FEATURE_NAMES` + `semantic`). */
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

export function MatchResultCard({ result, rank }: { result: MatchResult; rank: number }) {
  const features = Object.entries(result.feature_breakdown)
  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-accent-foreground">
            {rank}
          </span>
          <h3 className="font-semibold leading-tight">
            {result.matched_label || result.matched_id}
          </h3>
        </div>
        <ScoreMeter score={result.score} />
      </CardHeader>

      <CardContent className="space-y-5">
        {result.reasons.length > 0 && (
          <ul className="space-y-1.5">
            {result.reasons.map((reason, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        )}

        {features.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Score breakdown
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
