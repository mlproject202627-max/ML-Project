import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import type { ActivityEvent } from '../../data/types'
import { clockTime, cn, riskTone } from '../../lib/utils'
import { Avatar } from '../ui/Avatar'

const VERDICT_META: Record<
  ActivityEvent['verdict'],
  { label: string; className: string }
> = {
  normal: { label: 'normal', className: 'text-[var(--color-text-faint)] bg-[var(--color-surface)] ring-[var(--color-border)]' },
  notable: { label: 'notable', className: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]' },
  suspicious: { label: 'suspicious', className: 'text-[var(--color-critical)] bg-[var(--color-critical-bg)] ring-[var(--color-critical-border)]' },
}

export function EventFeed({
  live,
  limit = 12,
  height,
  className,
  onOpenEmployee,
  events = [],
}: {
  live: boolean
  limit?: number
  height?: number
  className?: string
  onOpenEmployee: (id: string) => void
  events?: ActivityEvent[]
}) {
  const [offset, setOffset] = useState(0)
  const count = events.length

  useEffect(() => {
    if (!live) return
    const t = window.setInterval(() => setOffset((o) => o + 1), 4200)
    return () => window.clearInterval(t)
  }, [live])

  if (count === 0) {
    return (
      <p className="px-4 py-12 text-center text-[11.5px] text-[var(--color-text-faint)]">
        No events match the current filter.
      </p>
    )
  }

  const start = offset % count
  const rotated = [...events.slice(start), ...events.slice(0, start)].slice(0, limit)

  return (
    <ul
      className={cn('scrollbar-none divide-y divide-[var(--color-border)] overflow-y-auto', className)}
      style={height ? { height } : undefined}
    >
      {rotated.map((ev, i) => {
        const tone = riskTone(ev.risk)
        const meta = VERDICT_META[ev.verdict]
        const name = ev.employeeName ?? ev.employeeId
        return (
          <li
            key={ev.id}
            className={cn(
              'flex items-center gap-3 px-3.5 py-2 transition-colors hover:bg-[var(--color-hover)]',
              i === 0 && live && 'animate-fade-up',
            )}
          >
            {ev.employeeInitials && (
              <button type="button" onClick={() => onOpenEmployee(ev.employeeId)} className="shrink-0">
                <Avatar initials={ev.employeeInitials} size={26} />
              </button>
            )}

            <span className="num w-[52px] shrink-0 text-[10.5px] text-[var(--color-text-faint)]">
              {clockTime(ev.ts)}
            </span>

            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-[11px]">
                <span className="truncate font-medium text-[var(--color-text)]">{ev.action}</span>
                <ArrowRight className="size-2.5 shrink-0 text-[var(--color-text-faint)]" />
                <span className="num truncate text-[var(--color-text-muted)]">{ev.target}</span>
              </p>
              <p className="mt-0.5 truncate text-[9.5px] text-[var(--color-text-faint)]">
                {name} · {ev.risk > 0 ? `risk ${ev.risk}` : 'no risk contribution'}
              </p>
            </div>

            <span
              className={cn(
                'hidden shrink-0 rounded-md px-1.5 py-0.5 text-[9.5px] font-medium tracking-wide ring-1 ring-inset sm:inline-flex',
                meta.className,
              )}
            >
              {meta.label}
            </span>

            <span className="num w-6 shrink-0 text-right text-[11px]" style={{ color: tone.hex }}>
              {ev.risk}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
