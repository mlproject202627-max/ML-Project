import type { ReactNode } from 'react'

export interface TooltipRow {
  label: string
  value: ReactNode
  color?: string
}

export function TooltipShell({ title, rows }: { title?: string; rows: TooltipRow[] }) {
  return (
    <div className="panel min-w-[168px] px-3 py-2.5">
      {title && (
        <p className="mb-1.5 text-[10px] font-semibold tracking-[0.12em] text-faint uppercase">
          {title}
        </p>
      )}
      <div className="space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5 text-[11px] text-muted">
              {r.color && (
                <span
                  className="size-1.5 rounded-full"
                  style={{ background: r.color }}
                />
              )}
              {r.label}
            </span>
            <span className="num text-[11px] font-medium text-fg">{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
