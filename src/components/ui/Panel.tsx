import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

interface PanelProps {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  interactive?: boolean
  padded?: boolean
}

export function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  interactive = false,
  padded = true,
}: PanelProps) {
  return (
    <section
      className={cn(
        'card animate-fade-up flex min-w-0 flex-col',
        interactive && 'card-hover cursor-pointer',
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-4 py-3">
          <div className="min-w-0">
            {title && (
              <h2 className="truncate text-[13px] font-semibold text-[var(--color-text)]">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="mt-0.5 truncate text-[11px] text-[var(--color-text-muted)]">{subtitle}</p>
            )}
          </div>
          {actions && (
            <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
          )}
        </header>
      )}
      <div className={cn('min-w-0 flex-1', padded && 'p-4', bodyClassName)}>
        {children}
      </div>
    </section>
  )
}
