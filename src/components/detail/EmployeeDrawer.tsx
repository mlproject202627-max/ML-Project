import { ArrowUpRight, Building2, Clock, MapPin, Timer, Users } from 'lucide-react'
import {
  BEHAVIOUR_AXES,
  KIND_META,
  SEVERITY_META,
  alertsForEmployee,
  employeeById,
  peerBaseline,
} from '../../data/mock'
import { Drawer } from '../ui/Drawer'
import { Avatar } from '../ui/Avatar'
import { SeverityBadge, StatusBadge, Tag } from '../ui/Badge'
import { RiskDial } from '../ui/RiskDial'
import { Meter } from '../ui/Meter'
import { BehaviourRadar } from '../charts/BehaviourRadar'
import { HourStrip } from '../charts/HourStrip'
import { relativeTime, riskTone } from '../../lib/utils'

const EMP_STATUS: Record<string, string> = {
  watchlist: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
  monitored: 'text-[var(--color-text-secondary)] bg-[var(--color-surface)] ring-[var(--color-border)]',
  cleared: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
}

export function EmployeeDrawer({ employeeId, onClose, onOpenAlert }: {
  employeeId: string | null
  onClose: () => void
  onOpenAlert: (id: string) => void
}) {
  const emp = employeeId ? employeeById(employeeId) : undefined
  if (!emp) {
    return (
      <Drawer open={false} onClose={onClose} title="">
        <span />
      </Drawer>
    )
  }

  const tone = riskTone(emp.riskScore)
  const peer = peerBaseline(emp)
  const myAlerts = alertsForEmployee(emp.id)

  return (
    <Drawer
      open={Boolean(employeeId)}
      onClose={onClose}
      width={520}
      title={
        <span className="flex items-center gap-2">
          {emp.name}
          <span className={`rounded-md px-1.5 py-0.5 text-[9.5px] font-semibold tracking-wider uppercase ring-1 ring-inset ${EMP_STATUS[emp.status]}`}>
            {emp.status}
          </span>
        </span>
      }
      subtitle={
        <span>
          {emp.title} · <span className="num">{emp.id}</span>
        </span>
      }
    >
      <div className="space-y-5">
        <div className="card flex items-center gap-4 p-3.5">
          <Avatar initials={emp.initials} department={emp.department} size={52} ring={tone.hex} />
          <div className="min-w-0 flex-1 space-y-1">
            <p className="text-[13px] font-semibold text-[var(--color-text)]">{emp.name}</p>
            <p className="text-[11px] text-[var(--color-text-muted)]">{emp.title}</p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5 text-[10px] text-[var(--color-text-faint)]">
              <span className="flex items-center gap-1">
                <Building2 className="size-3" /> {emp.department}
              </span>
              <span className="flex items-center gap-1">
                <MapPin className="size-3" /> {emp.location}
              </span>
              <span className="flex items-center gap-1">
                <Timer className="size-3" /> {emp.tenureMonths} mo tenure
              </span>
            </div>
          </div>
          <RiskDial score={emp.riskScore} size={72} sublabel="risk" />
        </div>

        <div className="card p-3.5">
          <div className="mb-1 flex items-start justify-between gap-3">
            <div>
              <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
                Behaviour vs peer group
              </h4>
              <p className="mt-0.5 text-[10px] text-[var(--color-text-faint)]">
                baseline: <span className="num">{emp.peerGroup}</span> mean
              </p>
            </div>
            <span className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
              <span className="size-1.5 rounded-full bg-[var(--color-text-muted)]" />
              this user
            </span>
          </div>
          <BehaviourRadar behaviour={emp.behaviour} baseline={peer} />
          <ul className="mt-1 grid grid-cols-2 gap-x-4 gap-y-2">
            {BEHAVIOUR_AXES.map((axis) => {
              const me = emp.behaviour[axis.key]
              const base = peer[axis.key]
              const delta = me - base
              return (
                <li key={axis.key} className="flex items-center gap-2">
                  <span className="w-[104px] shrink-0 truncate text-[10.5px] text-[var(--color-text-muted)]">
                    {axis.label}
                  </span>
                  <Meter value={me} color={delta > 25 ? 'var(--color-critical)' : 'var(--color-text-muted)'} height={4} className="flex-1" />
                  <span className={`num w-9 shrink-0 text-right text-[10px] ${delta > 25 ? 'text-[var(--color-critical)]' : delta > 10 ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-faint)]'}`}>
                    {delta > 0 ? '+' : ''}{delta}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-3.5 py-2.5">
            <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">Baseline drift</h4>
            <Tag>{`${emp.drift.toFixed(1)}σ from own baseline`}</Tag>
          </div>
          <table className="w-full text-left">
            <thead>
              <tr className="text-[9.5px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
                <th className="px-3.5 py-1.5 font-medium">Feature</th>
                <th className="px-2 py-1.5 font-medium">Baseline</th>
                <th className="px-2 py-1.5 font-medium">Current</th>
                <th className="px-3.5 py-1.5 text-right font-medium">Delta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {emp.baselineShift.map((row) => (
                <tr key={row.label} className="transition-colors hover:bg-[var(--color-hover)]">
                  <td className="px-3.5 py-2 text-[11px] text-[var(--color-text-muted)]">{row.label}</td>
                  <td className="num px-2 py-2 text-[11px] text-[var(--color-text-faint)]">{row.baseline}</td>
                  <td className="num px-2 py-2 text-[11px] text-[var(--color-text)]">{row.current}</td>
                  <td className="num px-3.5 py-2 text-right text-[11px] font-semibold text-[var(--color-critical)]">
                    {row.delta}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card p-3.5">
          <div className="mb-2.5 flex items-center justify-between">
            <h4 className="text-[11.5px] font-semibold text-[var(--color-text)]">
              Access intensity, last 24h
            </h4>
            <div className="flex items-center gap-2.5 text-[9.5px] text-[var(--color-text-faint)]">
              <span className="flex items-center gap-1">
                <span className="size-1.5 rounded-sm bg-[#22d3ee]" /> working hours
              </span>
              <span className="flex items-center gap-1">
                <span className="size-1.5 rounded-sm bg-[#a78bfa]" /> 22:00–06:00
              </span>
            </div>
          </div>
          <HourStrip hourly={emp.hourly} height={44} />
          <div className="num mt-1.5 flex justify-between text-[9px] text-[var(--color-text-faint)]">
            {['00', '04', '08', '12', '16', '20', '23'].map((h) => (
              <span key={h}>{h}</span>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="flex items-center gap-1.5 text-[11.5px] font-semibold text-[var(--color-text)]">
              <Users className="size-3.5 text-[var(--color-text-faint)]" /> Open detections
              <span className="num text-[var(--color-text-faint)]">({myAlerts.length})</span>
            </h4>
          </div>
          {myAlerts.length === 0 ? (
            <p className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-3 text-center text-[11px] text-[var(--color-text-faint)]">
              No detections in the selected window.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {myAlerts.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => onOpenAlert(a.id)}
                    className="card card-hover flex w-full items-center gap-2.5 p-2.5 text-left"
                  >
                    <span className="size-1.5 shrink-0 rounded-full" style={{ background: SEVERITY_META[a.severity].hex }} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[11.5px] text-[var(--color-text)]">{a.headline}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
                        <span className="num">{a.id}</span>·
                        <span>{KIND_META[a.kind].short}</span>·
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

        <div className="flex items-center gap-1.5 pb-1">
          <StatusBadge status="investigating" />
          <span className="text-[10px] text-[var(--color-text-faint)]">
            Assigned to Tier-2 · last reviewed 2 h ago
          </span>
        </div>
      </div>
    </Drawer>
  )
}
