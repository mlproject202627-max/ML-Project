import { ChevronRight, Clock } from 'lucide-react'
import { KIND_META, employeeById } from '../../data/mock'
import type { Alert } from '../../data/types'
import { relativeTime, riskTone } from '../../lib/utils'
import { Avatar } from '../ui/Avatar'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { Meter } from '../ui/Meter'

export function AlertRow({ alert, onOpen, variant = 'compact', active = false }: {
  alert: Alert
  onOpen: (id: string) => void
  variant?: 'compact' | 'full'
  active?: boolean
}) {
  const emp = employeeById(alert.employeeId)
  const kind = KIND_META[alert.kind]
  const tone = riskTone(alert.riskScore)

  return (
    <button
      type="button"
      onClick={() => onOpen(alert.id)}
      className={`group relative flex w-full items-center gap-3 border-b border-[var(--color-border)] px-3.5 py-2.5 text-left transition-colors duration-150 last:border-0 hover:bg-[var(--color-hover)] ${
        active ? 'bg-[var(--color-surface)]' : ''
      }`}
    >
      <span
        className="absolute top-0 bottom-0 left-0 w-[2px] opacity-60 transition-opacity duration-150 group-hover:opacity-100"
        style={{ background: tone.hex }}
      />

      {variant === 'full' && emp && (
        <Avatar initials={emp.initials} department={emp.department} size={32} ring={sevHex(alert.severity)} />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[12px] font-medium text-[var(--color-text)]">{alert.headline}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[10px] text-[var(--color-text-faint)]">
          <span className="num">{alert.id}</span>
          <span className="flex items-center gap-1">
            <span className="size-1.5 rounded-[3px]" style={{ background: kind.color }} />
            {kind.short}
          </span>
          {variant === 'full' && emp && (
            <span className="truncate">{emp.name} · {emp.department}</span>
          )}
          <span className="flex items-center gap-1">
            <Clock className="size-2.5" />
            {relativeTime(alert.detectedAt)}
          </span>
          {variant === 'full' && <span className="hidden xl:inline">{alert.asset}</span>}
        </div>
      </div>

      {variant === 'full' && (
        <div className="hidden w-[92px] shrink-0 lg:block">
          <div className="mb-1 flex items-center justify-between text-[9.5px] text-[var(--color-text-faint)]">
            <span>conf</span>
            <span className="num text-[var(--color-text-muted)]">{(alert.confidence * 100).toFixed(0)}%</span>
          </div>
          <Meter value={alert.confidence * 100} color="var(--color-text-muted)" height={3} />
        </div>
      )}

      {variant === 'full' && <StatusBadge status={alert.status} />}
      {variant === 'compact' && <SeverityBadge severity={alert.severity} showDot={false} />}

      <div className="w-[42px] shrink-0 text-right">
        <span className="num text-[15px] leading-none font-semibold" style={{ color: tone.hex }}>
          {alert.riskScore}
        </span>
        <p className="mt-0.5 text-[9px] text-[var(--color-text-faint)]">risk</p>
      </div>

      <ChevronRight className="size-3.5 shrink-0 text-[var(--color-text-faint)] transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-[var(--color-text)]" />
    </button>
  )
}

function sevHex(s: Alert['severity']): string {
  return { critical: '#DC2626', high: '#D97706', medium: '#2563EB', low: '#737373' }[s]
}
