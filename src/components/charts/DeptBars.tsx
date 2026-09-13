import { GRAPH } from '../../lib/utils'
import { Meter } from '../ui/Meter'

/** Colour ramp for the graph — severity stays legible inside the plot. */
function barColor(score: number): string {
  if (score >= 85) return GRAPH.alert
  if (score >= 70) return GRAPH.tertiary
  if (score >= 50) return GRAPH.secondary
  return GRAPH.primary
}

export function DeptBars({
  data,
}: {
  data: { department: string; count: number; meanRisk: number }[]
}) {
  return (
    <ul className="space-y-2.5">
      {data.map((d) => (
        <li key={d.department} className="flex items-center gap-3">
          <span className="w-[86px] shrink-0 truncate text-[11px] text-muted">
            {d.department}
          </span>
          <Meter
            value={d.meanRisk}
            color={barColor(d.meanRisk)}
            height={6}
            className="flex-1"
          />
          <span className="num w-9 shrink-0 text-right text-[11px] text-fg">
            {d.meanRisk.toFixed(1)}
          </span>
          <span className="num w-6 shrink-0 text-right text-[10px] text-faint">{d.count}</span>
        </li>
      ))}
    </ul>
  )
}
