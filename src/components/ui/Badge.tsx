import type { ReactNode } from 'react'
import { SEVERITY_META } from '../../data/mock'
import type { AlertStatus, Severity } from '../../data/types'
import { cn } from '../../lib/utils'

export function SeverityBadge({ severity, showDot = true }: { severity: Severity; showDot?: boolean }) {
  const colorMap: Record<Severity, string> = {
    critical: 'text-[var(--color-critical)] bg-[var(--color-critical-bg)] ring-[var(--color-critical-border)]',
    high: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    medium: 'text-[var(--color-info)] bg-[var(--color-info-bg)] ring-[var(--color-info-border)]',
    low: 'text-[var(--color-text-muted)] bg-[var(--color-surface)] ring-[var(--color-border)]',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-[0.09em] uppercase ring-1 ring-inset',
        colorMap[severity],
      )}
    >
      {showDot && <span className="size-1.5 rounded-full" style={{ background: 'currentColor' }} />}
      {SEVERITY_META[severity].label}
    </span>
  )
}

const STATUS_META: Record<AlertStatus, { label: string; className: string }> = {
  new: { label: 'New', className: 'text-[var(--color-info)] bg-[var(--color-info-bg)] ring-[var(--color-info-border)]' },
  investigating: { label: 'Investigating', className: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]' },
  contained: { label: 'Contained', className: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]' },
  dismissed: { label: 'Dismissed', className: 'text-[var(--color-text-faint)] bg-[var(--color-surface)] ring-[var(--color-border)]' },
}

export function StatusBadge({ status }: { status: AlertStatus }) {
  const meta = STATUS_META[status]
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium tracking-wide ring-1 ring-inset',
        meta.className,
      )}
    >
      {meta.label}
    </span>
  )
}

export function Chip({ children, className, active = false, onClick }: { children: ReactNode; className?: string; active?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md border px-2 py-1 text-[11px] font-medium whitespace-nowrap transition-colors duration-150',
        active
          ? 'border-[var(--color-primary)] bg-[var(--color-primary)] text-[var(--color-primary-text)]'
          : 'border-[var(--color-border)] bg-transparent text-[var(--color-text-secondary)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]',
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Tag({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-text-muted)]',
        className,
      )}
    >
      {children}
    </span>
  )
}
