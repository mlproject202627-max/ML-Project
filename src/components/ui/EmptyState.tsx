import type { ReactNode } from 'react'
import { Search } from 'lucide-react'

export function EmptyState({
  icon,
  title,
  description,
  actions,
}: {
  icon?: ReactNode
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-full bg-[var(--color-surface)]">
        {icon || <Search className="size-5 text-[var(--color-text-muted)]" />}
      </div>
      <h3 className="text-[14px] font-semibold text-[var(--color-text)]">{title}</h3>
      {description && (
        <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-[var(--color-text-muted)]">
          {description}
        </p>
      )}
      {actions && <div className="mt-4 flex items-center gap-2">{actions}</div>}
    </div>
  )
}
