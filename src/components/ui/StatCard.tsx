import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Sparkline } from './Sparkline'

export function StatCard({ label, value, unit, delta, deltaGood, icon, color = '#737373', spark, footnote, onClick }: {
  label: string
  value: string
  unit?: string
  delta?: string
  deltaGood?: boolean
  icon?: ReactNode
  color?: string
  spark?: number[]
  footnote?: string
  onClick?: () => void
}) {
  const positive = delta?.startsWith('+')
  const good = deltaGood ? positive : !positive

  return (
    <div
      onClick={onClick}
      className={cn(
        'card animate-fade-up group relative p-4',
        onClick && 'card-hover cursor-pointer',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.14em] text-[var(--color-text-faint)] uppercase">
            {label}
          </p>
          <div className="mt-2 flex items-baseline gap-1.5">
            <span className="num text-[26px] leading-none font-semibold text-[var(--color-text)]">
              {value}
            </span>
            {unit && <span className="text-[11px] text-[var(--color-text-faint)]">{unit}</span>}
          </div>
        </div>
        {icon && (
          <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-muted)] transition-colors duration-150 group-hover:border-[var(--color-border-strong)] group-hover:text-[var(--color-text)]">
            {icon}
          </span>
        )}
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          {delta && (
            <span
              className={cn(
                'num text-[11px] font-medium',
                good ? 'text-[var(--color-success)]' : 'text-[var(--color-text-faint)]',
              )}
            >
              {delta}
            </span>
          )}
          {footnote && <span className="text-[10px] text-[var(--color-text-faint)]">{footnote}</span>}
        </div>
        {spark && <Sparkline data={spark} color={color} />}
      </div>
    </div>
  )
}
