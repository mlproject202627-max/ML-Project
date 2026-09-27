import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ActivityEvent } from '../../data/types'
import { KIND_META } from '../../data/mock'
import { GRAPH, clockTime, cn } from '../../lib/utils'
import { Panel } from '../ui/Panel'
import { Chip } from '../ui/Badge'
import { ErrorState } from '../ui/ErrorState'
import { LoadingState } from '../ui/LoadingState'
import { ActivityHeatmap } from '../charts/ActivityHeatmap'
import { EventFeed } from '../lists/EventFeed'
import { TooltipShell } from '../charts/ChartTooltip'
import { activityFromTimelineList, alertsFromApi } from '../../lib/adapters'
import { getThreatTimeline, listAlerts } from '../../lib/adminApi'
import { useApiResource } from '../../lib/useApi'

type FeedFilter = 'all' | ActivityEvent['verdict']

/**
 * How many telemetry rows the panel aggregates over.
 *
 * The two charts below bucket these rows by weekday and by clock hour, so the
 * shape they draw is only as honest as the sample behind it. The server caps a
 * page at 200; asking for the cap makes the picture representative of recent
 * activity rather than of the last handful of events.
 */
const WINDOW = 200

export function Timeline({ live, onSelectAlert, onSelectEmployee }: {
  live: boolean
  onSelectAlert: (id: string) => void
  onSelectEmployee: (id: string) => void
}) {
  const [feedFilter, setFeedFilter] = useState<FeedFilter>('all')

  const alertsRes = useApiResource(
    () => listAlerts({ sort: 'recent', page_size: 100 }),
    [],
  )
  const eventsRes = useApiResource(
    () => getThreatTimeline({ page_size: WINDOW }),
    [],
  )

  const recentAlerts = useMemo(
    () => (alertsRes.data ? alertsFromApi(alertsRes.data.items) : []),
    [alertsRes.data],
  )
  const events = useMemo(
    () => (eventsRes.data ? activityFromTimelineList(eventsRes.data.items) : []),
    [eventsRes.data],
  )

  // Both charts are aggregations of the events actually retrieved, not a
  // separate dataset — there is no second source for "access intensity", and
  // drawing one from anything else would be inventing it.
  const heatGrid = useMemo(() => {
    const out: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0))
    for (const ev of events) {
      const d = new Date(ev.ts)
      if (Number.isNaN(d.getTime())) continue
      const day = (d.getUTCDay() + 6) % 7 // Monday-first
      out[day][d.getUTCHours()] += 1
    }
    const peak = Math.max(1, ...out.flat())
    return out.map((row) => row.map((v) => Math.round((v / peak) * 100)))
  }, [events])

  const hourly = useMemo(() => {
    const totals = Array(24).fill(0) as number[]
    for (const ev of events) {
      const d = new Date(ev.ts)
      if (Number.isNaN(d.getTime())) continue
      totals[d.getUTCHours()] += 1
    }
    return totals.map((v, h) => ({ hour: `${String(h).padStart(2, '0')}`, value: v }))
  }, [events])

  const timeline = useMemo(() => recentAlerts.slice(0, 8), [recentAlerts])

  const filteredEvents = useMemo(
    () => (feedFilter === 'all' ? events : events.filter((e) => e.verdict === feedFilter)),
    [feedFilter, events],
  )

  const sevColor = (s: string) => ({ critical: '#DC2626', high: '#D97706', medium: '#2563EB', low: '#737373' }[s] || '#737373')

  if (alertsRes.loading || eventsRes.loading) {
    return (
      <div className="space-y-4">
        <TimelineHeading />
        <LoadingState rows={6} />
      </div>
    )
  }

  if (alertsRes.error || eventsRes.error) {
    return (
      <div className="space-y-4">
        <TimelineHeading />
        <ErrorState
          title="Could not load the activity timeline"
          description={alertsRes.error ?? eventsRes.error ?? ''}
          onRetry={() => {
            alertsRes.reload()
            eventsRes.reload()
          }}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <TimelineHeading />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" title="Access intensity by weekday and hour" subtitle="Aggregated across all monitored identities">
          <ActivityHeatmap grid={heatGrid} height={220} />
        </Panel>

        <Panel className="xl:col-span-5" title="Hour-of-day distribution" subtitle="Mean access volume per clock hour">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={hourly} margin={{ top: 8, right: 6, bottom: 0, left: -22 }}>
              <CartesianGrid stroke={GRAPH.grid} strokeDasharray="3 5" vertical={false} />
              <XAxis dataKey="hour" tick={{ fill: GRAPH.tick, fontSize: 9.5 }} tickLine={false} axisLine={{ stroke: GRAPH.axis }} interval={2} />
              <YAxis tick={{ fill: GRAPH.tick, fontSize: 9.5 }} tickLine={false} axisLine={false} width={40} />
              <Tooltip
                cursor={{ fill: 'rgba(0,0,0,0.03)' }}
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null
                  const h = Number(label)
                  const isNight = h < 6 || h >= 22
                  return (
                    <TooltipShell
                      title={`${label}:00 – ${String((h + 1) % 24).padStart(2, '0')}:00`}
                      rows={[
                        { label: 'Mean volume', value: payload[0].value as number, color: isNight ? GRAPH.secondary : GRAPH.primary },
                        { label: 'Window', value: isNight ? 'off-hours' : 'working hours' },
                      ]}
                    />
                  )
                }}
              />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {hourly.map((d) => {
                  const h = Number(d.hour)
                  const isNight = h < 6 || h >= 22
                  return <Cell key={d.hour} fill={isNight ? GRAPH.secondary : GRAPH.primary} fillOpacity={isNight ? 0.85 : 0.62} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" title="Detection timeline" subtitle="When each open detection fired, most recent first" padded={false}>
          <ol className="relative px-4 py-4">
            <span className="absolute top-6 bottom-6 left-[26px] w-px bg-gradient-to-b from-[var(--color-border)] via-[var(--color-border)] to-transparent" />
            {timeline.map((a) => {
              const subjectId = a.employeeId
              const hex = sevColor(a.severity)
              return (
                <li key={a.id} className="relative flex gap-4 pb-5 last:pb-0">
                  <span className="relative z-10 mt-1.5 grid size-[13px] shrink-0 place-items-center">
                    <span className="absolute size-[13px] rounded-full opacity-20" style={{ background: hex }} />
                    <span className="size-[7px] rounded-full" style={{ background: hex }} />
                  </span>
                  <div className="group min-w-0 flex-1 rounded-lg border border-transparent px-2 py-1 transition-colors duration-150 hover:border-[var(--color-border)] hover:bg-[var(--color-hover)]">
                    <button type="button" onClick={() => onSelectAlert(a.id)} className="block w-full text-left">
                      <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                        <span className="num text-[10.5px] text-[var(--color-text-faint)]">{clockTime(a.detectedAt)} UTC</span>
                        <span className="num text-[10.5px] font-medium text-[var(--color-text)]">{a.id}</span>
                        <span className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 py-px text-[9.5px] font-semibold tracking-wide text-[var(--color-text-muted)] uppercase">
                          {KIND_META[a.kind].short}
                        </span>
                        <span className="num ml-auto text-[10.5px]" style={{ color: hex }}>
                          risk {a.riskScore}
                        </span>
                      </span>
                      <span className="mt-1 block truncate text-[11.5px] text-[var(--color-text)]">{a.headline}</span>
                    </button>
                    <p className="mt-0.5 truncate text-[10px] text-[var(--color-text-faint)]">
                      <button
                        type="button"
                        onClick={() => onSelectEmployee(subjectId)}
                        className="text-[var(--color-text-muted)] underline decoration-dotted underline-offset-2 hover:text-[var(--color-text)]"
                      >
                        {a.employeeName ?? subjectId}
                      </button>{' '}
                      · {a.asset}
                    </p>
                  </div>
                </li>
              )
            })}
          </ol>
        </Panel>

        <Panel className="xl:col-span-5" title="Access event stream" subtitle={`${filteredEvents.length} events in the current window`} padded={false}
          actions={
            <div className="flex gap-1.5">
              {(['all', 'notable', 'suspicious'] as FeedFilter[]).map((f) => (
                <Chip key={f} active={feedFilter === f} onClick={() => setFeedFilter(f)}>
                  {f}
                </Chip>
              ))}
            </div>
          }
        >
          <EventFeed live={live} limit={11} height={430} onOpenEmployee={onSelectEmployee} events={filteredEvents} />
        </Panel>
      </div>

      <Panel title="Anomaly class reference" subtitle="What each detector family looks for" padded={false}>
        <div className="grid grid-cols-1 divide-y divide-[var(--color-border)] md:grid-cols-2 md:divide-y-0 xl:grid-cols-4">
          {(Object.keys(KIND_META) as (keyof typeof KIND_META)[]).map((k) => {
            const meta = KIND_META[k]
            const count = recentAlerts.filter((a) => a.kind === k).length
            return (
              <div key={k} className={cn('border-[var(--color-border)] p-3.5 transition-colors duration-150 hover:bg-[var(--color-hover)]', 'md:border-r md:last:border-r-0 xl:border-b-0')}>
                <div className="flex items-center gap-2">
                  <span className="size-2 rounded-[3px]" style={{ background: meta.color }} />
                  <span className="text-[11.5px] font-semibold text-[var(--color-text)]">{meta.label}</span>
                  <span className="num ml-auto text-[11px] text-[var(--color-text-faint)]">{count}</span>
                </div>
                <p className="mt-1.5 text-[10.5px] leading-relaxed text-[var(--color-text-faint)]">{meta.description}</p>
              </div>
            )
          })}
        </div>
      </Panel>
    </div>
  )
}

function TimelineHeading() {
  return (
    <div className="mb-2">
      <h1 className="text-[20px] font-bold text-[var(--color-text)]">Activity Timeline</h1>
      <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
        Review chronological activity across users and systems.
      </p>
    </div>
  )
}
