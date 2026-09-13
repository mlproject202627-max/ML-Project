import { GRAPH } from '../../lib/utils'

export function HourStrip({
  hourly,
  accent = GRAPH.primary,
  height = 34,
}: {
  hourly: number[]
  accent?: string
  height?: number
}) {
  return (
    <div className="flex items-end gap-[2px]" style={{ height }}>
      {hourly.map((v, h) => {
        const night = h < 6 || h >= 22
        return (
          <div
            key={h}
            title={`${String(h).padStart(2, '0')}:00 — ${v}`}
            className="flex-1 rounded-[2px] transition-all duration-300 hover:opacity-100"
            style={{
              height: `${Math.max(8, v)}%`,
              background: night ? GRAPH.secondary : accent,
              opacity: 0.22 + (v / 100) * 0.62,
            }}
          />
        )
      })}
    </div>
  )
}
