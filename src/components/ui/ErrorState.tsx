import { RefreshCw } from 'lucide-react'

export function ErrorState({
  title = 'Something went wrong',
  description = 'The system could not load the requested data.',
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-full bg-[var(--color-critical-bg)]">
        <span className="text-[var(--color-critical)] text-lg">!</span>
      </div>
      <h3 className="text-[14px] font-semibold text-[var(--color-text)]">{title}</h3>
      <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-[var(--color-text-muted)]">
        {description}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-3.5 py-2 text-[12px] font-medium text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)]"
        >
          <RefreshCw className="size-3.5" />
          Retry
        </button>
      )}
    </div>
  )
}
