import { useState } from 'react'
import { DAYS } from '../../lib/utils'

const STOPS: [number, [number, number, number]][] = [
  [0, [26, 22, 18]],
  [22, [20, 54, 66]],
  [45, [14, 116, 144]],
  [68, [34, 211, 238]],
  [86, [167, 139, 250]],
  [100, [251, 90, 118]],
]

function ramp(v: number): string {
  const t = Math.max(0, Math.min(100, v))
  for (let i = 0; i < STOPS.length - 1; i++) {
    const [lo, c1] = STOPS[i]
    const [hi, c2] = STOPS[i + 1]
    if (t >= lo && t <= hi) {
      const f = (t - lo) / (hi - lo || 1)
      const rgb = c1.map((c, k) => Math.round(c + (c2[k] - c) * f))
      return `rgb(${rgb[0]} ${rgb[1]} ${rgb[2]})`
    }
  }
  return 'rgb(251 90 118)'
}

export function ActivityHeatmap({
  grid,
  height = 216,
}: {
  /** grid[day][hour] → intensity 0–100 */
  grid: number[][]
  height?: number
}) {
  const [hover, setHover] = useState<{ day: number; hour: number; v: number } | null>(null)

  return (
    <div className="flex min-w-0 gap-2">
      <div className="flex shrink-0 flex-col justify-between py-[2px] text-[9px] text-faint">
        {DAYS.map((d) => (
          <span key={d} className="flex flex-1 items-center">
            {d}
          </span>
        ))}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-col gap-[3px]" style={{ height }}>
          {grid.map((row, day) => (
            <div key={day} className="flex flex-1 gap-[3px]">
              {row.map((v, hour) => (
                <div
                  key={hour}
                  onMouseEnter={() => setHover({ day, hour, v })}
                  onMouseLeave={() => setHover(null)}
                  title={`${DAYS[day]} ${String(hour).padStart(2, '0')}:00 — intensity ${v}`}
                  className="flex-1 cursor-crosshair rounded-[3px] transition-[transform,box-shadow] duration-150 hover:scale-[1.35] hover:shadow-[0_0_10px_2px_rgba(34,211,238,0.25)]"
                  style={{
                    background: ramp(v),
                    opacity: 0.35 + (v / 100) * 0.65,
                    transform: hover?.day === day && hover?.hour === hour ? 'scale(1.35)' : undefined,
                  }}
                />
              ))}
            </div>
          ))}
        </div>

        <div className="mt-2 flex items-center justify-between text-[9px] text-faint">
          <div className="flex gap-[3px]">
            {[0, 6, 12, 18, 23].map((h) => (
              <span key={h} className="w-[26px] shrink-0">
                {String(h).padStart(2, '0')}
              </span>
            ))}
          </div>
          <span className="num h-3.5 text-fg">
            {hover
              ? `${DAYS[hover.day]} ${String(hover.hour).padStart(2, '0')}:00 · ${hover.v}`
              : 'hover a cell'}
          </span>
        </div>
      </div>
    </div>
  )
}
