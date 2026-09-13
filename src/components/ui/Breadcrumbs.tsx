import { ChevronRight, Home } from 'lucide-react'

export function Breadcrumbs({ items }: { items: string[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1 text-[12px]">
      <Home className="size-3.5 text-[var(--color-text-faint)]" />
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1">
          <ChevronRight className="size-3 text-[var(--color-text-faint)]" />
          <span
            className={
              i === items.length - 1
                ? 'font-medium text-[var(--color-text)]'
                : 'text-[var(--color-text-muted)]'
            }
          >
            {item}
          </span>
        </span>
      ))}
    </nav>
  )
}
