import { useMemo, type ReactNode } from 'react'
import {
  ArrowUpRight,
  Building2,
  Clock,
  Download,
  MapPin,
  Monitor,
  ShieldAlert,
  Usb,
} from 'lucide-react'
import { Drawer } from '../ui/Drawer'
import { Avatar } from '../ui/Avatar'
import { SeverityBadge } from '../ui/Badge'
import { RiskDial } from '../ui/RiskDial'
import { Meter } from '../ui/Meter'
import { LoadingState } from '../ui/LoadingState'
import { ErrorState } from '../ui/ErrorState'
import { initialsFromName, alertsFromApi, activityFromTimelineList } from '../../lib/adapters'
import { getEmployeeDetail, type EmployeeDetail } from '../../lib/adminApi'
import { useApiResource } from '../../lib/useApi'
import { relativeTime, riskTone } from '../../lib/utils'

/**
 * The employee-monitoring case file.
 *
 * Every panel here is assembled from `GET /api/v1/admin/employees/{id}`, which
 * returns the risk assessment, its reasons, the risk history and the windowed
 * activity in one response. The panels it replaced drew a six-axis behaviour
 * radar, a peer-group baseline comparison and a per-feature baseline-drift
 * table — none of which any endpoint produces, and all of which rendered
 * plausible-looking shapes because the numbers behind them were written by
 * hand.
 *
 * Data-flow note: every collection this drawer renders is normalised once,
 * right after the fetch, through `Array.isArray` guards into a plain local
 * binding. The JSX below then reads only those bindings — never `data.<key>`
 * directly — so a missing or null key degrades to an empty panel instead of
 * throwing during render and blanking the whole app (there is no error
 * boundary above this drawer; the first version of this file crashed the
 * entire console on `undefined.map` because it read `data.locations`, a field
 * the endpoint has never returned).
 */
export function EmployeeDrawer({ employeeId, onClose, onOpenAlert }: {
  employeeId: string | null
  onClose: () => void
  onOpenAlert: (id: string) => void
}) {
  const { data, error, loading, reload } = useApiResource<EmployeeDetail | null>(
    () => (employeeId ? getEmployeeDetail(employeeId) : Promise.resolve(null)),
    [employeeId],
  )

  /* -- Normalisation ---------------------------------------------------
   * The endpoint returns collections as explicit keys — empty rather than
   * absent when there is nothing to report — but the drawer is one contract
   * change or stale cache away from a missing key, and `Array.isArray` is
   * the honest guard: `??` alone still throws on a `null` that arrived in
   * the JSON, because `.map` on `null` is a TypeError, not a fallback.
   * Every derived array below reads through one of these bindings. */
  const emp = data?.employee ?? null

  /* The engine guarantees a `risk` object (zero-scored when never measured),
   * but an employee whose assessment has not been written yet could come
   * back without one, and the dial and meters would throw on
   * `undefined.toFixed`. Numbers are type-checked rather than trusted. */
  const risk = useMemo(() => {
    const r = data?.risk
    if (r == null || typeof r !== 'object') return null
    return {
      score: typeof r.score === 'number' ? r.score : 0,
      level: r.level ?? 'LOW',
      change: typeof r.change === 'number' ? r.change : 0,
      ruleScore: typeof r.ruleScore === 'number' ? r.ruleScore : 0,
      mlScore: typeof r.mlScore === 'number' ? r.mlScore : 0,
      baselineScore: typeof r.baselineScore === 'number' ? r.baselineScore : 0,
      timestamp: r.timestamp ?? null,
      reasons: Array.isArray(r.reasons) ? r.reasons : ([] as string[]),
    }
  }, [data])

  const events = useMemo(
    () =>
      data && Array.isArray(data.timeline) ? activityFromTimelineList(data.timeline) : [],
    [data],
  )
  const alerts = useMemo(
    () => (data && Array.isArray(data.alerts) ? alertsFromApi(data.alerts) : []),
    [data],
  )
  const locations = useMemo(
    () => (data && Array.isArray(data.locationHistory) ? data.locationHistory : []),
    [data],
  )
  const devices = useMemo(
    () => (data && Array.isArray(data.deviceHistory) ? data.deviceHistory : []),
    [data],
  )
  /* Downloads and USB transfers arrive as individual events, not aggregates;
   * the per-resource counts the panels show are derived here — the one place
   * that knows the event shape. */
  const downloads = useMemo(() => {
    if (!data || !Array.isArray(data.downloads)) return []
    const counts = new Map<string, number>()
    for (const d of data.downloads) {
      const key = d.resource || 'Unknown resource'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()].map(([label, count]) => ({ label, count }))
  }, [data])
  const usbEvents = useMemo(() => {
    if (!data || !Array.isArray(data.usbEvents)) return []
    const counts = new Map<string, number>()
    for (const u of data.usbEvents) {
      const key = u.device || 'Unknown device'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return [...counts.entries()].map(([label, count]) => ({ label, count }))
  }, [data])
  const riskHistory = useMemo(
    () => (data && Array.isArray(data.riskHistory) ? data.riskHistory : []),
    [data],
  )

  // 24 hourly buckets, counted from the events actually returned. This is the
  // one "access intensity" figure the data supports; the mock drew an
  // intensity curve with no unit behind it.
  const hourly = useMemo(() => {
    const out = Array(24).fill(0) as number[]
    for (const ev of events) {
      const d = new Date(ev.ts)
      if (!Number.isNaN(d.getTime())) out[d.getUTCHours()] += 1
    }
    return out
  }, [events])
  const hourlyPeak = Math.max(1, ...hourly)

  if (!employeeId) return null

  const tone = riskTone(risk?.score ?? 0)
  const isNight = (h: number) => h < 6 || h >= 22

  return (
    <Drawer
      open={Boolean(employeeId)}
      onClose={onClose}
      width={520}
      title={emp ? emp.name : loading ? 'Loading risk assessment…' : 'Employee'}
      subtitle={
        emp ? (
          <span>
            {emp.jobTitle ?? emp.role ?? 'Employee'}
            {emp.employeeCode ? <> · <span className="num">{emp.employeeCode}</span></> : null}
          </span>
        ) : undefined
      }
    >
      {loading ? (
        <div className="p-1">
          <LoadingState rows={4} />
        </div>
      ) : error ? (
        <ErrorState title="Could not load this employee" description={error} onRetry={reload} />
      ) : !emp || !risk ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="mb-3 grid size-10 place-items-center rounded-full bg-[var(--color-surface)]">
            <ShieldAlert className="size-4 text-[var(--color-text-faint)]" />
          </div>
          <p className="text-[13px] font-semibold text-[var(--color-text)]">
            No risk assessment data available.
          </p>
          <p className="mt-1 max-w-xs text-[11.5px] leading-relaxed text-[var(--color-text-muted)]">
            Sentinel has not produced an assessment for this employee yet. Re-run detection from
            the monitoring queue, then reopen this case file.
          </p>
        </div>
      ) : (
        <div className="space-y-5">
          {/* Identity */}
          <div className="card flex items-center gap-4 p-3.5">
            <Avatar initials={initialsFromName(emp.name)} size={52} ring={tone.hex} />
            <div className="min-w-0 flex-1 space-y-1">
              <p className="text-[13px] font-semibold text-[var(--color-text)]">{emp.name}</p>
              <p className="text-[11px] text-[var(--color-text-muted)]">
                {emp.jobTitle ?? emp.role ?? '—'}
              </p>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5 text-[10px] text-[var(--color-text-faint)]">
                {emp.department && (
                  <span className="flex items-center gap-1">
                    <Building2 className="size-3" /> {emp.department}
                  </span>
                )}
                {emp.branchName && (
                  <span className="flex items-center gap-1">
                    <MapPin className="size-3" /> {emp.branchName}
                  </span>
                )}
                {emp.lastLogin && (
                  <span className="flex items-center gap-1">
                    <Clock className="size-3" /> last login {relativeTime(emp.lastLogin)}
                  </span>
                )}
              </div>
            </div>
            <RiskDial score={risk.score} size={72} sublabel="risk" />
          </div>

          {/* Why the score is what it is */}
          <div className="card p-3.5">
            <div className="mb-2 flex items-baseline justify-between">
              <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
                Risk assessment
              </h4>
              <span className="num text-[11px] font-semibold" style={{ color: tone.hex }}>
                {risk.score.toFixed(1)} · {risk.level}
              </span>
            </div>

            {/* The three components the engine actually combines. */}
            <div className="space-y-2.5">
              {[
                { label: 'Rule evidence', value: risk.ruleScore },
                { label: 'ML anomaly', value: risk.mlScore },
                { label: 'Baseline deviation', value: risk.baselineScore },
              ].map((c) => (
                <div key={c.label} className="flex items-center gap-3">
                  <span className="w-[112px] shrink-0 text-[10.5px] text-[var(--color-text-muted)]">
                    {c.label}
                  </span>
                  <Meter value={c.value} color="var(--color-text-muted)" height={4} className="flex-1" />
                  <span className="num w-9 shrink-0 text-right text-[10px] text-[var(--color-text-faint)]">
                    {c.value.toFixed(0)}
                  </span>
                </div>
              ))}
            </div>

            <ul className="mt-3 space-y-1.5 border-t border-[var(--color-border)] pt-3">
              {risk.reasons.length === 0 ? (
                <li className="text-[11px] text-[var(--color-text-faint)]">
                  No rule fired and activity is consistent with this employee's baseline.
                </li>
              ) : (
                risk.reasons.map((r) => (
                  <li key={r} className="text-[11px] leading-relaxed text-[var(--color-text-secondary)]">
                    {r}
                  </li>
                ))
              )}
            </ul>
          </div>

          {/* Where the activity comes from — real aggregates, real counts */}
          <div className="grid grid-cols-2 gap-3">
            <AggregateCard
              icon={<MapPin className="size-3" />}
              title="Locations"
              rows={locations.map((r) => ({ label: r.city ?? '', count: r.count }))}
              empty="No location variation recorded."
            />
            <AggregateCard
              icon={<Monitor className="size-3" />}
              title="Devices"
              rows={devices.map((r) => ({ label: r.device ?? '', count: r.count }))}
              empty="No device variation recorded."
            />
            <AggregateCard
              icon={<Download className="size-3" />}
              title="Sensitive downloads"
              rows={downloads}
              empty="No downloads in the window."
            />
            <AggregateCard
              icon={<Usb className="size-3" />}
              title="Removable media"
              rows={usbEvents}
              empty="No simulated USB activity."
            />
          </div>

          {/* Access intensity, counted from the returned events */}
          <div className="card p-3.5">
            <div className="mb-2.5 flex items-center justify-between">
              <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
                Access intensity by hour
              </h4>
              <span className="text-[9.5px] text-[var(--color-text-faint)]">
                {events.length} events in window
              </span>
            </div>
            <div className="flex h-11 items-end gap-[2px]">
              {hourly.map((v, h) => (
                <span
                  key={h}
                  title={`${String(h).padStart(2, '0')}:00 — ${v} event${v === 1 ? '' : 's'}`}
                  className="flex-1 rounded-[2px]"
                  style={{
                    height: `${Math.max(2, (v / hourlyPeak) * 100)}%`,
                    background: isNight(h) ? '#a78bfa' : '#22d3ee',
                    opacity: v === 0 ? 0.15 : 1,
                  }}
                />
              ))}
            </div>
            <div className="num mt-1.5 flex justify-between text-[9px] text-[var(--color-text-faint)]">
              {['00', '04', '08', '12', '16', '20', '23'].map((h) => (
                <span key={h}>{h}</span>
              ))}
            </div>
          </div>

          {/* Risk history — appended to, never rewritten */}
          {riskHistory.length > 0 && (
            <div className="card overflow-hidden">
              <div className="border-b border-[var(--color-border)] px-3.5 py-2.5">
                <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
                  Risk history
                </h4>
              </div>
              <ul className="divide-y divide-[var(--color-border)]">
                {riskHistory.slice(-6).reverse().map((r) => (
                  <li key={`${r.timestamp}-${r.score}`} className="flex items-center gap-3 px-3.5 py-2">
                    <span className="num w-12 shrink-0 text-[11px] font-semibold" style={{ color: riskTone(r.score).hex }}>
                      {r.score.toFixed(0)}
                    </span>
                    <span className="num w-20 shrink-0 text-[10px] text-[var(--color-text-faint)]">
                      {r.level}
                    </span>
                    <span className="num ml-auto text-[10px] text-[var(--color-text-faint)]">
                      {r.timestamp ? relativeTime(r.timestamp) : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Detections */}
          <div>
            <h4 className="mb-2 flex items-center gap-1.5 text-[11.5px] font-semibold text-[var(--color-text)]">
              <ShieldAlert className="size-3.5 text-[var(--color-text-faint)]" /> Detections
              <span className="num text-[var(--color-text-faint)]">({alerts.length})</span>
            </h4>
            {alerts.length === 0 ? (
              <p className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-3 text-center text-[11px] text-[var(--color-text-faint)]">
                No detections recorded for this employee.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {alerts.map((a) => (
                  <li key={a.id}>
                    <button
                      type="button"
                      onClick={() => onOpenAlert(a.id)}
                      className="card card-hover flex w-full items-center gap-2.5 p-2.5 text-left"
                    >
                      <span
                        className="size-1.5 shrink-0 rounded-full"
                        style={{ background: riskTone(a.riskScore).hex }}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[11.5px] text-[var(--color-text)]">{a.headline}</p>
                        <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
                          <Clock className="size-2.5" />
                          {relativeTime(a.detectedAt)}
                        </p>
                      </div>
                      <SeverityBadge severity={a.severity} showDot={false} />
                      <ArrowUpRight className="size-3 shrink-0 text-[var(--color-text-faint)]" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Drawer>
  )
}

/** One "where did the activity come from" panel: a label and a count.
 *  Callers normalise their aggregate's label field to `label` at the call
 *  site, which keeps this free of index-signature lookups and `String()`
 *  casts over an untyped `Record`. */
function AggregateCard({
  icon,
  title,
  rows,
  empty,
}: {
  icon: ReactNode
  title: string
  rows: { label: string; count: number }[]
  empty: string
}) {
  const clean = rows.filter((r) => r.label)
  const peak = Math.max(1, ...clean.map((r) => r.count))

  return (
    <div className="card p-3">
      <div className="flex items-center gap-1.5 text-[var(--color-text-faint)]">
        {icon}
        <span className="text-[10px]">{title}</span>
      </div>
      {clean.length === 0 ? (
        <p className="mt-1.5 text-[10.5px] text-[var(--color-text-faint)]">{empty}</p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {clean.slice(0, 3).map((r) => (
            <li key={r.label} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-[10.5px] text-[var(--color-text)]">
                {r.label}
              </span>
              <span className="num shrink-0 text-[10px] text-[var(--color-text-faint)]">
                {r.count}
              </span>
              <Meter
                value={(r.count / peak) * 100}
                color="var(--color-text-faint)"
                height={3}
                className="w-8 shrink-0"
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
