import { ChevronRight, MapPin } from 'lucide-react'
import type { Employee } from '../../data/types'
import { riskTone } from '../../lib/utils'
import { Avatar } from '../ui/Avatar'
import { RiskDial } from '../ui/RiskDial'
import { HourStrip } from '../charts/HourStrip'

export function IdentityRow({ employee, rank, onOpen }: {
  employee: Employee
  rank?: number
  onOpen: (id: string) => void
}) {
  const tone = riskTone(employee.riskScore)

  return (
    <button
      type="button"
      onClick={() => onOpen(employee.id)}
      className="group flex w-full items-center gap-3 border-b border-[var(--color-border)] px-3.5 py-2.5 text-left transition-colors duration-150 last:border-0 hover:bg-[var(--color-hover)]"
    >
      {rank !== undefined && (
        <span className="num w-4 shrink-0 text-[11px] text-[var(--color-text-faint)]">{rank}</span>
      )}

      <Avatar
        initials={employee.initials}
        department={employee.department}
        size={34}
        ring={employee.status === 'watchlist' ? tone.hex : undefined}
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[12px] font-medium text-[var(--color-text)]">{employee.name}</span>
          {employee.status === 'watchlist' && (
            <span className="shrink-0 rounded-full bg-[var(--color-warning-bg)] px-1.5 py-px text-[9px] font-semibold tracking-wide text-[var(--color-warning)] uppercase ring-1 ring-[var(--color-warning-border)] ring-inset">
              watch
            </span>
          )}
        </div>
        <p className="mt-0.5 flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
          <span className="truncate">{employee.title}</span>
          <span className="hidden items-center gap-1 sm:flex">
            <MapPin className="size-2.5" />
            {employee.location}
          </span>
        </p>
      </div>

      <div className="hidden w-[96px] shrink-0 lg:block">
        <HourStrip hourly={employee.hourly} accent={tone.hex} height={24} />
      </div>

      <div className="w-[46px] shrink-0 text-right">
        <span className="num text-[11px] font-medium" style={{ color: tone.hex }}>
          {employee.drift > 0 ? '+' : ''}{employee.drift.toFixed(1)}σ
        </span>
        <p className="mt-0.5 text-[9px] text-[var(--color-text-faint)]">drift</p>
      </div>

      <RiskDial score={employee.riskScore} size={44} stroke={4} />

      <ChevronRight
        className="size-3.5 shrink-0 text-[var(--color-text-faint)] transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-[var(--color-text)]"
      />
    </button>
  )
}
