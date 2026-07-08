/**
 * The match-score meter. Per the dataviz method, the bar uses ONE hue (indigo `primary`) to encode
 * magnitude; the *tier word* ("Strong/Moderate/Weak fit") carries the categorical meaning in a
 * semantic color, so the signal is never color-alone.
 */

import { cn } from '@/lib/utils'

export function scoreTier(score: number): { label: string; className: string } {
  if (score >= 0.66) return { label: 'Strong fit', className: 'text-success' }
  if (score >= 0.4) return { label: 'Moderate fit', className: 'text-warning' }
  return { label: 'Weak fit', className: 'text-muted-foreground' }
}

const clampPct = (v: number) => Math.round(Math.max(0, Math.min(1, v)) * 100)

export function ScoreMeter({ score, className }: { score: number; className?: string }) {
  const pct = clampPct(score)
  const tier = scoreTier(score)
  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-baseline justify-between">
        <span className={cn('text-sm font-semibold', tier.className)}>{tier.label}</span>
        <span className="text-sm font-medium tabular-nums text-muted-foreground">{pct}%</span>
      </div>
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-secondary"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Match score: ${tier.label}, ${pct} percent`}
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

/** A slim single-feature bar used inside the score breakdown grid. */
export function FeatureBar({ label, value }: { label: string; value: number }) {
  const pct = clampPct(value)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">{pct}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <div className="h-full rounded-full bg-primary/70" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
