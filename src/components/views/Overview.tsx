import { useMemo } from 'react'
import {
  Activity,
  ArrowUpRight,
  Gauge,
  ShieldAlert,
  Users,
} from 'lucide-react'
import type { AnomalyKind } from '../../data/types'
import { formatCompact, formatNumber } from '../../lib/utils'
import { Panel } from '../ui/Panel'
import { StatCard } from '../ui/StatCard'
import { ErrorState } from '../ui/ErrorState'
import { LoadingState } from '../ui/LoadingState'
import { ActivityHeatmap } from '../charts/ActivityHeatmap'
import { DeptBars } from '../charts/DeptBars'
import { KindDonut, type KindSlice } from '../charts/KindDonut'
import { RiskTrendChart } from '../charts/RiskTrendChart'
import { AlertRow } from '../lists/AlertRow'
import { EventFeed } from '../lists/EventFeed'
import { IdentityRow, type RiskRowData } from '../lists/IdentityRow'
import type { Range } from '../layout/PageHeader'
import { activityFromTimelineList, alertsFromApi, initialsFromName } from '../../lib/adapters'
import { getAdminDashboard, getThreatTimeline, listAlerts } from '../../lib/adminApi'
import { useApiResource } from '../../lib/useApi'

/** Rows the derived panels aggregate over. See `Timeline` for the rationale. */
const WINDOW = 200

export function Overview({ live, range, onSelectAlert, onSelectEmployee, onOpenQueue }: {
  live: boolean
  range: Range
  onSelectAlert: (id: string) => void
  onSelectEmployee: (id: string) => void
  onOpenQueue: () => void
}) {
  const dashRes = useApiResource(() => getAdminDashboard(), [])
  const alertsRes = useApiResource(() => listAlerts({ sort: 'risk', page_size: 100 }), [])
  const eventsRes = useApiResource(() => getThreatTimeline({ page_size: WINDOW }), [])

  const alerts = useMemo(
    () => (alertsRes.data ? alertsFromApi(alertsRes.data.items) : []),
    [alertsRes.data],
  )
  const events = useMemo(
    () => (eventsRes.data ? activityFromTimelineList(eventsRes.data.items) : []),
    [eventsRes.data],
  )

  /* -- KPI cards ---------------------------------------------------- */

  const cards = dashRes.data?.cards
  const ranking = useMemo(
    () => dashRes.data?.charts.employeeRiskRanking ?? [],
    [dashRes.data],
  )
  const meanRisk = useMemo(() => {
    if (ranking.length === 0) return 0
    return ranking.reduce((sum, r) => sum + r.riskScore, 0) / ranking.length
  }, [ranking])

  /* -- Trend: detections per day, and the mean risk of that day's events */

  const trend = useMemo(() => {
    const points = dashRes.data?.charts.threatsOverTime ?? []
    const byDay = new Map<string, { total: number; risk: number; count: number }>()
    for (const ev of events) {
      const key = ev.ts.slice(0, 10)
      const bucket = byDay.get(key) ?? { total: 0, risk: 0, count: 0 }
      bucket.risk += ev.risk
      bucket.count += 1
      byDay.set(key, bucket)
    }
    return points.map((p) => {
      const day = p.date.slice(0, 10)
      const bucket = byDay.get(day)
      return {
        label: p.date,
        anomalies: p.count,
        meanRisk: bucket && bucket.count > 0 ? Math.round(bucket.risk / bucket.count) : 0,
        // `baseline` is left undefined on purpose: no endpoint produces a
        // baseline series, and a zero-filled one would draw a flat line at the
        // floor that reads as a measurement. The chart omits the series.
      }
    })
  }, [dashRes.data, events])

  /* -- Detection mix ------------------------------------------------ */

  const kindSlices = useMemo<KindSlice[]>(() => {
    const map = new Map<AnomalyKind, number>()
    for (const a of alerts) map.set(a.kind, (map.get(a.kind) ?? 0) + 1)
    return [...map.entries()]
      .map(([kind, count]) => ({ kind, count }))
      .sort((a, b) => b.count - a.count)
  }, [alerts])

  /* -- Heatmap: bucketed from the events actually retrieved ---------- */

  const heatGrid = useMemo(() => {
    const out: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0))
    for (const ev of events) {
      const d = new Date(ev.ts)
      if (Number.isNaN(d.getTime())) continue
      out[(d.getUTCDay() + 6) % 7][d.getUTCHours()] += 1
    }
    const peak = Math.max(1, ...out.flat())
    return out.map((row) => row.map((v) => Math.round((v / peak) * 100)))
  }, [events])

  /* -- Priority triage ---------------------------------------------- */

  const triage = useMemo(
    () =>
      [...alerts]
        .sort((a, b) => {
          const rank = { new: 0, investigating: 1, contained: 2, dismissed: 3 }
          return rank[a.status] - rank[b.status] || b.riskScore - a.riskScore
        })
        .slice(0, 6),
    [alerts],
  )

  /* -- Risk ranking and department roll-up -------------------------- */

  const drift = useMemo<RiskRowData[]>(
    () =>
      ranking.slice(0, 6).map((r) => ({
        id: r.id,
        name: r.name,
        initials: initialsFromName(r.name),
        department: r.department,
        jobTitle: r.department,
        branchName: r.branchName,
        riskScore: Math.round(r.riskScore),
        riskLevel: r.riskLevel,
        riskChange: 0,
        openAlerts: alerts.filter((a) => a.employeeId === r.id && a.status !== 'contained' && a.status !== 'dismissed').length,
      })),
    [ranking, alerts],
  )

  const departments = useMemo(() => {
    const byDept = new Map<string, { count: number; risk: number }>()
    for (const r of ranking) {
      const key = r.department || 'Unassigned'
      const bucket = byDept.get(key) ?? { count: 0, risk: 0 }
      bucket.count += 1
      bucket.risk += r.riskScore
      byDept.set(key, bucket)
    }
    return [...byDept.entries()]
      .map(([department, b]) => ({
        department,
        count: b.count,
        meanRisk: Math.round(b.risk / b.count),
      }))
      .sort((a, b) => b.meanRisk - a.meanRisk)
      .slice(0, 7)
  }, [ranking])

  const loading = dashRes.loading || alertsRes.loading || eventsRes.loading
  const error = dashRes.error ?? alertsRes.error ?? eventsRes.error

  if (loading) {
    return (
      <div className="space-y-4">
        <OverviewHeading />
        <LoadingState rows={5} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <OverviewHeading />
        <ErrorState
          title="Could not load the command center"
          description={error}
          onRetry={() => {
            dashRes.reload()
            alertsRes.reload()
            eventsRes.reload()
          }}
        />
      </div>
    )
  }

  const sparkAnomalies = trend.map((t) => t.anomalies)
  const sparkRisk = trend.map((t) => t.meanRisk)

  return (
    <div className="space-y-4">
      <OverviewHeading />

      {/* KPI Cards — every figure is a live count; there is no stored history
          to compare against, so no card claims a change against a prior period. */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Open alerts"
          value={String(cards?.openAlerts ?? 0)}
          icon={<ShieldAlert className="size-4" />}
          footnote={`${cards?.criticalAlerts ?? 0} critical`}
          spark={sparkAnomalies}
        />
        <StatCard
          label="Identities watched"
          value={formatNumber(cards?.employeesMonitored ?? 0)}
          icon={<Users className="size-4" />}
          footnote={`${cards?.activeEmployees ?? 0} active employees`}
          spark={sparkRisk}
        />
        <StatCard
          label="Anomalies detected"
          value={formatCompact(cards?.threatsToday ?? 0)}
          icon={<Activity className="size-4" />}
          footnote={`today · window ${range}`}
          spark={sparkAnomalies}
        />
        <StatCard
          label="Mean risk index"
          value={meanRisk.toFixed(1)}
          unit="/100"
          icon={<Gauge className="size-4" />}
          footnote={`across ${ranking.length} monitored`}
          spark={sparkRisk}
        />
      </div>

      {/* Trend + Detection Mix */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-8"
          title="Detection volume vs mean risk"
          subtitle="Detections per day, and the mean risk contribution of that day's events"
          actions={
            <div className="hidden items-center gap-3 text-[10px] text-[var(--color-text-faint)] sm:flex">
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-[2px] bg-[#22d3ee]" /> detections
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 rounded-[2px] bg-gradient-to-r from-[#a78bfa] to-[#fb5a76]" /> mean risk
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

      {/* Triage + Ranking */}
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
            {triage.length === 0 ? (
              <p className="px-4 py-12 text-center text-[11.5px] text-[var(--color-text-faint)]">
                No detections recorded yet.
              </p>
            ) : (
              triage.map((a) => <AlertRow key={a.id} alert={a} onOpen={onSelectAlert} />)
            )}
          </div>
        </Panel>

        <Panel className="xl:col-span-5" title="Highest risk employees" subtitle="Current composite risk, highest first" padded={false}>
          <div>
            {drift.length === 0 ? (
              <p className="px-4 py-12 text-center text-[11.5px] text-[var(--color-text-faint)]">
                No employees under monitoring.
              </p>
            ) : (
              drift.map((e, i) => (
                <IdentityRow key={e.id} employee={e} rank={i + 1} onOpen={onSelectEmployee} />
              ))
            )}
          </div>
        </Panel>
      </div>

      {/* Heatmap + Dept + Feed */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-5" title="Access intensity" subtitle={`Bucketed from the last ${events.length} telemetry events`}>
          <ActivityHeatmap grid={heatGrid} height={206} />
        </Panel>

        <Panel className="xl:col-span-3" title="Risk by department" subtitle="Mean composite score">
          <DeptBars data={departments} />
        </Panel>

        <Panel
          className="xl:col-span-4"
          title="Live access stream"
          subtitle="Most recent telemetry across the estate"
          padded={false}
          actions={
            <span className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
              <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-[var(--color-success)]' : 'bg-[var(--color-text-faint)]'}`} />
              {live ? 'streaming' : 'paused'}
            </span>
          }
        >
          <EventFeed live={live} height={248} onOpenEmployee={onSelectEmployee} events={events} />
        </Panel>
      </div>
    </div>
  )
}

function OverviewHeading() {
  return (
    <div className="mb-2">
      <h1 className="text-[20px] font-bold text-[var(--color-text)]">Command Center</h1>
      <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
        Monitor organizational risk, detected anomalies, and active investigations from one place.
      </p>
    </div>
  )
}
