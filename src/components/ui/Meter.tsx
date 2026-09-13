import { cn } from '../../lib/utils'

export function Meter({ value, color = 'var(--color-text-muted)', height = 3, className }: {
  value: number
  color?: string
  height?: number
  className?: string
}) {
  const pct = Math.max(0, Math.min(100, value))
  return (
    <div className={cn('relative w-full overflow-hidden rounded-full bg-[var(--color-surface)]', className)} style={{ height }}>
      <div
        className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-300"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  )
}
