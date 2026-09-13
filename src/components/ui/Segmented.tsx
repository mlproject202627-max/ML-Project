import { cn } from '../../lib/utils'

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  size = 'md',
  className,
}: {
  options: { value: T; label: string }[]
  value: T
  onChange: (v: T) => void
  size?: 'sm' | 'md'
  className?: string
}) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5',
        className,
      )}
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(o.value)}
            className={cn(
              'relative rounded-md font-medium transition-colors duration-150',
              size === 'sm' ? 'px-2 py-1 text-[10px]' : 'px-2.5 py-1.5 text-[11px]',
              active
                ? 'bg-[var(--color-card)] text-[var(--color-text)] shadow-sm'
                : 'text-[var(--color-text-faint)] hover:text-[var(--color-text-muted)]',
            )}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}
