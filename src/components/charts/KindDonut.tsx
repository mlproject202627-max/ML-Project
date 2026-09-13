import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { KIND_META } from '../../data/mock'
import type { AnomalyKind } from '../../data/types'
import { TooltipShell } from './ChartTooltip'

export interface KindSlice {
  kind: AnomalyKind
  count: number
}

export function KindDonut({
  data,
  height = 200,
}: {
  data: KindSlice[]
  height?: number
}) {
  const total = data.reduce((s, d) => s + d.count, 0)

  return (
    <div className="flex items-center gap-1">
      <div className="relative shrink-0" style={{ width: height, height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const slice = payload[0].payload as KindSlice
                return (
                  <TooltipShell
                    title={KIND_META[slice.kind].label}
                    rows={[
                      { label: 'Alerts', value: slice.count, color: KIND_META[slice.kind].color },
                      { label: 'Share', value: `${Math.round((slice.count / total) * 100)}%` },
                    ]}
                  />
                )
              }}
            />
            <Pie
              data={data}
              dataKey="count"
              nameKey="kind"
              innerRadius="62%"
              outerRadius="88%"
              paddingAngle={3}
              stroke="none"
              startAngle={90}
              endAngle={-270}
            >
              {data.map((d) => (
                <Cell
                  key={d.kind}
                  fill={KIND_META[d.kind].color}
                  style={{ filter: `drop-shadow(0 0 6px ${KIND_META[d.kind].color}55)` }}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="num text-[24px] leading-none font-semibold text-fg">{total}</span>
          <span className="mt-1 text-[9px] tracking-[0.16em] text-faint uppercase">
            Alerts
          </span>
        </div>
      </div>

      <ul className="min-w-0 flex-1 space-y-1.5">
        {data.map((d) => (
          <li key={d.kind} className="flex items-center gap-2">
            <span
              className="size-2 shrink-0 rounded-[3px]"
              style={{
                background: KIND_META[d.kind].color,
                boxShadow: `0 0 8px ${KIND_META[d.kind].color}66`,
              }}
            />
            <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
              {KIND_META[d.kind].label}
            </span>
            <span className="num text-[11px] text-faint">{d.count}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
