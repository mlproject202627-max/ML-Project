import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function Drawer({ open, onClose, title, subtitle, children, footer, width = 460 }: {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  footer?: ReactNode
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <div
      aria-hidden={!open}
      className={cn(
        'fixed inset-0 z-50 flex justify-end',
        open ? 'pointer-events-auto' : 'pointer-events-none',
      )}
    >
      <div
        onClick={onClose}
        className={cn(
          'absolute inset-0 bg-black/30 transition-opacity duration-300',
          open ? 'opacity-100' : 'opacity-0',
        )}
      />

      <div
        style={{ width: `min(${width}px, 100vw)` }}
        className={cn(
          'relative flex h-full flex-col border-l border-[var(--color-border)] bg-[var(--color-card)] shadow-xl transition-transform duration-300 ease-out',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-4 py-3.5">
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-[var(--color-text)]">{title}</div>
            {subtitle && <div className="mt-0.5 text-[11px] text-[var(--color-text-faint)]">{subtitle}</div>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
          >
            <X className="size-3.5" />
          </button>
        </header>

        <div className="scrollbar-none min-h-0 flex-1 overflow-y-auto p-4">{children}</div>

        {footer && (
          <footer className="border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}
