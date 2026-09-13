import type { ContributingFactor } from '../../data/types'
import { GRAPH } from '../../lib/utils'
import { Meter } from '../ui/Meter'

export function FactorBars({
  factors,
  accent = GRAPH.secondary,
}: {
  factors: ContributingFactor[]
  accent?: string
}) {
  const max = Math.max(...factors.map((f) => f.weight), 0.01)

  return (
    <ul className="space-y-3">
      {factors.map((f) => {
        const pct = (f.weight / max) * 100
        return (
          <li key={f.label} className="group">
            <div className="mb-1.5 flex items-baseline justify-between gap-3">
              <span className="truncate text-[11px] font-medium text-fg">{f.label}</span>
              <span className="num shrink-0 text-[11px] font-semibold" style={{ color: accent }}>
                {(f.weight * 100).toFixed(0)}%
              </span>
            </div>
            <Meter value={pct} color={accent} height={5} />
            <p className="mt-1 truncate text-[10px] text-faint">{f.detail}</p>
          </li>
        )
      })}
    </ul>
  )
}
