export function LoadingState({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <div className="skeleton size-10 shrink-0 rounded-lg" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="skeleton h-3.5 w-1/3 rounded" />
            <div className="skeleton h-3 w-2/3 rounded" />
          </div>
          <div className="skeleton h-6 w-16 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  )
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-4">
            <div className="skeleton h-3 w-20 rounded" />
            <div className="skeleton mt-3 h-7 w-16 rounded" />
            <div className="skeleton mt-2 h-2.5 w-full rounded" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <div className="card h-[300px] lg:col-span-8 skeleton" />
        <div className="card h-[300px] lg:col-span-4 skeleton" />
      </div>
    </div>
  )
}
