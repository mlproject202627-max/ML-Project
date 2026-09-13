import { useMemo } from 'react'
import {
  Activity,
  ArrowUpRight,
  Gauge,
  ShieldAlert,
  Users,
} from 'lucide-react'
import {
  alerts,
  departmentBreakdown,
  employees,
  heatmap,
  summary,
  trend,
} from '../../data/mock'
import type { AnomalyKind } from '../../data/types'
import { formatCompact, formatNumber } from '../../lib/utils'
import { Panel } from '../ui/Panel'
import { StatCard } from '../ui/StatCard'
import { ActivityHeatmap } from '../charts/ActivityHeatmap'
import { DeptBars } from '../charts/DeptBars'
import { KindDonut, type KindSlice } from '../charts/KindDonut'
import { RiskTrendChart } from '../charts/RiskTrendChart'
import { AlertRow } from '../lists/AlertRow'
import { EventFeed } from '../lists/EventFeed'
import { IdentityRow } from '../lists/IdentityRow'
import type { Range } from '../layout/PageHeader'

export function Overview({ live, range, onSelectAlert, onSelectEmployee, onOpenQueue }: {
  live: boolean
  range: Range
  onSelectAlert: (id: string) => void
  onSelectEmployee: (id: string) => void
  onOpenQueue: () => void
}) {
  const kindSlices = useMemo<KindSlice[]>(() => {
    const map = new Map<AnomalyKind, number>()
    for (const a of alerts) map.set(a.kind, (map.get(a.kind) ?? 0) + 1)
    return [...map.entries()]
      .map(([kind, count]) => ({ kind, count }))
      .sort((a, b) => b.count - a.count)
  }, [])

  const heatGrid = useMemo(() => {
    const out: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0))
    for (const c of heatmap) out[c.day][c.hour] = c.intensity
    return out
  }, [])

  const triage = useMemo(
    () =>
      [...alerts]
        .sort((a, b) => {
          const rank = { new: 0, investigating: 1, contained: 2, dismissed: 3 }
          return rank[a.status] - rank[b.status] || b.riskScore - a.riskScore
        })
        .slice(0, 6),
    [],
  )

  const drift = useMemo(
    () =>
      [...employees]
        .filter((e) => e.status !== 'cleared')
        .sort((a, b) => b.drift - a.drift)
        .slice(0, 6),
    [],
  )

  const rangeScale = { '24h': 1, '7d': 6.4, '30d': 27.5, '90d': 82 }[range]
  const anomalies = Math.round(trend.reduce((s, t) => s + t.anomalies, 0) * (rangeScale / 3.2))

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div className="mb-2">
        <h1 className="text-[20px] font-bold text-[var(--color-text)]">Command Center</h1>
        <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
          Monitor organizational risk, detected anomalies, and active investigations from one place.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Open alerts" value={String(summary.activeAlerts)} delta="+4 vs prev" icon={<ShieldAlert className="size-4" />} footnote={`${summary.criticalAlerts} critical`} spark={trend.map((t) => t.anomalies)} />
        <StatCard label="Identities watched" value={formatNumber(summary.monitored)} delta={`+${summary.monitoredDelta}%`} deltaGood icon={<Users className="size-4" />} footnote="estate-wide UEBA" spark={trend.map((t) => t.meanRisk)} />
        <StatCard label="Anomalies detected" value={formatCompact(anomalies)} delta="+18.2%" icon={<Activity className="size-4" />} footnote={`window ${range}`} spark={trend.map((t) => t.anomalies + t.meanRisk / 4)} />
        <StatCard label="Mean risk index" value={summary.meanRisk.toFixed(1)} unit="/100" delta="+9.1" icon={<Gauge className="size-4" />} footnote="queue weighted" spark={trend.map((t) => t.meanRisk)} />
      </div>

      {/* Trend + Detection Mix */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-8"
          title="Anomaly volume vs mean risk index"
          subtitle="Composite of all active detectors"
          actions={
            <div className="hidden items-center gap-3 text-[10px] text-[var(--color-text-faint)] sm:flex">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-[2px] bg-[#22d3ee]" /> anomalies
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-[2px] bg-gradient-to-r from-[#a78bfa] to-[#fb5a76]" /> risk
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-[2px] bg-[var(--color-text-faint)]" /> baseline
              </span>
            </div>
          }
        >
          <RiskTrendChart data={trend} height={252} />
        </Panel>

        <Panel className="xl:col-span-4" title="Detection mix" subtitle="Alerts by behavioural anomaly class">
          <KindDonut data={kindSlices} height={186} />
        </Panel>
      </div>

      {/* Triage + Drift */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Priority triage"
          subtitle="Unresolved detections ranked by composite risk"
          padded={false}
          actions={
            <button
              type="button"
              onClick={onOpenQueue}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] bg-transparent px-2 py-1 text-[10.5px] font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            >
              Open queue <ArrowUpRight className="size-3" />
            </button>
          }
        >
          <div>
            {triage.map((a) => (
              <AlertRow key={a.id} alert={a} onOpen={onSelectAlert} />
            ))}
          </div>
        </Panel>

        <Panel className="xl:col-span-5" title="Highest behaviour drift" subtitle="Distance from peer-group centroid, in standard deviations" padded={false}>
          <div>
            {drift.map((e, i) => (
              <IdentityRow key={e.id} employee={e} rank={i + 1} onOpen={onSelectEmployee} />
            ))}
          </div>
        </Panel>
      </div>

      {/* Heatmap + Dept + Feed */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-5" title="Access intensity" subtitle="7-day rolling window, all monitored identities">
          <ActivityHeatmap grid={heatGrid} height={206} />
        </Panel>

        <Panel className="xl:col-span-3" title="Risk by department" subtitle="Mean composite score">
          <DeptBars data={departmentBreakdown} />
        </Panel>

        <Panel
          className="xl:col-span-4"
          title="Live access stream"
          subtitle="Normalised access events across the estate"
          padded={false}
          actions={
            <span className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
              <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-[var(--color-success)]' : 'bg-[var(--color-text-faint)]'}`} />
              {live ? 'streaming' : 'paused'}
            </span>
          }
        >
          <EventFeed live={live} height={248} onOpenEmployee={onSelectEmployee} />
        </Panel>
      </div>
    </div>
  )
}
