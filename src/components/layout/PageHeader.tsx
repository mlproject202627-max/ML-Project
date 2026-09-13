import { Download, RefreshCw } from 'lucide-react'
import { Segmented } from '../ui/Segmented'
import type { NavItem } from '../../lib/nav'

export type Range = '24h' | '7d' | '30d' | '90d'

export function PageHeader({ item, range, onRange }: { item: NavItem; range: Range; onRange: (r: Range) => void }) {
  return (
    <div className="flex shrink-0 flex-col gap-3 border-b border-line-soft bg-black px-4 py-2.5 lg:flex-row lg:items-center lg:gap-4 lg:px-5">
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[14.5px] leading-tight font-semibold text-white">
          {item.label}
        </h1>
        <p className="mt-0.5 truncate text-[11px] text-faint">{item.blurb}</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Segmented
          size="sm"
          value={range}
          onChange={onRange}
          options={[
            { value: '24h', label: '24H' },
            { value: '7d', label: '7D' },
            { value: '30d', label: '30D' },
            { value: '90d', label: '90D' },
          ]}
        />

        <button
          type="button"
          title="Refresh feeds"
          className="grid size-8 place-items-center rounded-lg border border-line text-muted transition-colors duration-150 hover:border-line-hover hover:bg-surface-2 hover:text-fg"
        >
          <RefreshCw className="size-3.5" />
        </button>

        <button
          type="button"
          title="Export snapshot"
          className="hidden size-8 place-items-center rounded-lg border border-line text-muted transition-colors duration-150 hover:border-line-hover hover:bg-surface-2 hover:text-fg sm:grid"
        >
          <Download className="size-3.5" />
        </button>
      </div>
    </div>
  )
}
