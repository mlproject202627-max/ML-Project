import { useMemo, useState } from 'react'
import { ArrowUpDown, Filter, Search } from 'lucide-react'
import { KIND_META, SEVERITY_META, alerts } from '../../data/mock'
import type { AlertStatus, AnomalyKind, Severity } from '../../data/types'
import { Chip } from '../ui/Badge'
import { Panel } from '../ui/Panel'
import { Segmented } from '../ui/Segmented'
import { AlertRow } from '../lists/AlertRow'
import { cn } from '../../lib/utils'

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']
const STATUSES: AlertStatus[] = ['new', 'investigating', 'contained', 'dismissed']

export function Alerts({ query, onSelectAlert, selectedAlertId }: {
  query: string
  onSelectAlert: (id: string) => void
  selectedAlertId: string | null
}) {
  const [severity, setSeverity] = useState<Severity | 'all'>('all')
  const [status, setStatus] = useState<AlertStatus | 'all'>('all')
  const [kind, setKind] = useState<AnomalyKind | 'all'>('all')
  const [sort, setSort] = useState<'risk' | 'recent' | 'confidence'>('risk')

  const counts = useMemo(() => {
    const out = { critical: 0, high: 0, medium: 0, low: 0 } as Record<Severity, number>
    for (const a of alerts) out[a.severity] += 1
    return out
  }, [])

  const kinds = useMemo(() => [...new Set(alerts.map((a) => a.kind))] as AnomalyKind[], [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return alerts
      .filter((a) => (severity === 'all' ? true : a.severity === severity))
      .filter((a) => (status === 'all' ? true : a.status === status))
      .filter((a) => (kind === 'all' ? true : a.kind === kind))
      .filter((a) =>
        q
          ? a.id.toLowerCase().includes(q) ||
            a.headline.toLowerCase().includes(q) ||
            a.asset.toLowerCase().includes(q) ||
            a.employeeId.toLowerCase().includes(q) ||
            KIND_META[a.kind].label.toLowerCase().includes(q)
          : true,
      )
      .sort((a, b) => {
        if (sort === 'recent') return b.detectedAt.localeCompare(a.detectedAt)
        if (sort === 'confidence') return b.confidence - a.confidence
        return b.riskScore - a.riskScore
      })
  }, [severity, status, kind, sort, query])

  const sevColors: Record<Severity, { bg: string; border: string; text: string; dot: string }> = {
    critical: { bg: 'bg-[var(--color-critical-bg)]', border: 'ring-[var(--color-critical-border)]', text: 'text-[var(--color-critical)]', dot: 'bg-[var(--color-critical)]' },
    high: { bg: 'bg-[var(--color-warning-bg)]', border: 'ring-[var(--color-warning-border)]', text: 'text-[var(--color-warning)]', dot: 'bg-[var(--color-warning)]' },
    medium: { bg: 'bg-[var(--color-info-bg)]', border: 'ring-[var(--color-info-border)]', text: 'text-[var(--color-info)]', dot: 'bg-[var(--color-info)]' },
    low: { bg: 'bg-[var(--color-surface)]', border: 'ring-[var(--color-border)]', text: 'text-[var(--color-text-muted)]', dot: 'bg-[var(--color-text-faint)]' },
  }

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div className="mb-2">
        <h1 className="text-[20px] font-bold text-[var(--color-text)]">Anomaly Queue</h1>
        <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
          Review suspicious behavioural patterns detected by Sentinel.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {SEVERITIES.map((s) => {
          const meta = SEVERITY_META[s]
          const colors = sevColors[s]
          const active = severity === s
          return (
            <button
              key={s}
              type="button"
              onClick={() => setSeverity(active ? 'all' : s)}
              className={cn(
                'card card-hover flex items-center gap-3 p-3.5 text-left transition-all',
                active && `ring-2 ring-inset ${colors.border}`
              )}
            >
              <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${colors.bg}`}>
                <span className={`size-2.5 rounded-full ${colors.dot}`} />
              </span>
              <div className="min-w-0">
                <p className={`num text-[20px] leading-none font-semibold ${colors.text}`}>{counts[s]}</p>
                <p className="mt-1 text-[10px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">{meta.label}</p>
              </div>
            </button>
          )
        })}
      </div>

      <Panel
        title="Anomaly queue"
        subtitle={`${filtered.length} of ${alerts.length} detections match the current filters`}
        padded={false}
        actions={
          <div className="flex items-center gap-2">
            <Segmented size="sm" value={sort} onChange={setSort} options={[{ value: 'risk', label: 'Risk' }, { value: 'recent', label: 'Recent' }, { value: 'confidence', label: 'Confidence' }]} />
            <span className="hidden items-center gap-1 text-[10px] text-[var(--color-text-faint)] sm:flex">
              <ArrowUpDown className="size-3" /> sort
            </span>
          </div>
        }
      >
        <div className="flex flex-wrap items-center gap-3 border-b border-[var(--color-border)] px-3.5 py-3">
          <span className="flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
            <Filter className="size-3" /> Status
          </span>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={status === 'all'} onClick={() => setStatus('all')}>All</Chip>
            {STATUSES.map((s) => (
              <Chip key={s} active={status === s} onClick={() => setStatus(s)}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </Chip>
            ))}
          </div>

          <span className="ml-2 hidden text-[10px] font-semibold tracking-[0.1em] text-[var(--color-text-faint)] uppercase lg:block">Class</span>
          <div className="flex flex-wrap gap-1.5">
            <Chip active={kind === 'all'} onClick={() => setKind('all')}>All</Chip>
            {kinds.map((k) => (
              <Chip key={k} active={kind === k} onClick={() => setKind(k)}>
                <span className="flex items-center gap-1.5">
                  <span className="size-1.5 rounded-[2px]" style={{ background: KIND_META[k].color }} />
                  {KIND_META[k].short}
                </span>
              </Chip>
            ))}
          </div>

          {query && (
            <span className="ml-auto flex items-center gap-1.5 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[10.5px] text-[var(--color-text-secondary)]">
              <Search className="size-3" />
              "{query}"
            </span>
          )}
        </div>

        {filtered.length === 0 ? (
          <p className="px-4 py-14 text-center text-[12px] text-[var(--color-text-faint)]">No detections match these filters.</p>
        ) : (
          <div>
            {filtered.map((a) => (
              <AlertRow key={a.id} alert={a} onOpen={onSelectAlert} variant="full" active={a.id === selectedAlertId} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
