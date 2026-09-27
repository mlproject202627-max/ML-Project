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

  const events = useMemo(
    () => (data ? activityFromTimelineList(data.activity ?? []) : []),
    [data],
  )
  const alerts = useMemo(() => (data ? alertsFromApi(data.alerts ?? []) : []), [data])

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

  const emp = data?.employee
  const risk = data?.risk
  const tone = riskTone(risk?.score ?? 0)
  const isNight = (h: number) => h < 6 || h >= 22

  return (
    <Drawer
      open={Boolean(employeeId)}
      onClose={onClose}
      width={520}
      title={emp ? emp.name : 'Loading…'}
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
        <span />
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
              rows={data.locations.map((r) => ({ label: r.city, count: r.count }))}
              empty="No location variation recorded."
            />
            <AggregateCard
              icon={<Monitor className="size-3" />}
              title="Devices"
              rows={data.devices.map((r) => ({ label: r.device, count: r.count }))}
              empty="No device variation recorded."
            />
            <AggregateCard
              icon={<Download className="size-3" />}
              title="Sensitive downloads"
              rows={data.downloads.map((r) => ({ label: r.resource, count: r.count }))}
              empty="No downloads in the window."
            />
            <AggregateCard
              icon={<Usb className="size-3" />}
              title="Removable media"
              rows={data.usbEvents.map((r) => ({ label: r.device, count: r.count }))}
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
          {data.riskHistory.length > 0 && (
            <div className="card overflow-hidden">
              <div className="border-b border-[var(--color-border)] px-3.5 py-2.5">
                <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
                  Risk history
                </h4>
              </div>
              <ul className="divide-y divide-[var(--color-border)]">
                {data.riskHistory.slice(-6).reverse().map((r) => (
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
