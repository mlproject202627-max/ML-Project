import { useMemo, useState } from 'react'
import {
  ArrowUpDown,
  ChevronRight,
  Gauge,
  MapPin,
  ShieldAlert,
  Users,
} from 'lucide-react'
import {
  alertsForEmployee,
  employees,
  peerBaseline,
  summary,
} from '../../data/mock'
import type { Department } from '../../data/types'
import { cn, formatNumber, riskTone } from '../../lib/utils'
import { Avatar } from '../ui/Avatar'
import { Chip } from '../ui/Badge'
import { Panel } from '../ui/Panel'
import { RiskDial } from '../ui/RiskDial'
import { Segmented } from '../ui/Segmented'
import { StatCard } from '../ui/StatCard'
import { HourStrip } from '../charts/HourStrip'
import { BehaviourRadar } from '../charts/BehaviourRadar'

type SortKey = 'risk' | 'drift' | 'name' | 'alerts'

export function Behaviour({ query, onSelectEmployee, selectedEmployeeId }: {
  query: string
  onSelectEmployee: (id: string) => void
  selectedEmployeeId: string | null
}) {
  const [dept, setDept] = useState<Department | 'all'>('all')
  const [sort, setSort] = useState<SortKey>('risk')

  const departments = useMemo(
    () => [...new Set(employees.map((e) => e.department))].sort() as Department[],
    [],
  )

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return employees
      .filter((e) => (dept === 'all' ? true : e.department === dept))
      .filter((e) =>
        q
          ? e.name.toLowerCase().includes(q) ||
            e.title.toLowerCase().includes(q) ||
            e.peerGroup.toLowerCase().includes(q) ||
            e.id.toLowerCase().includes(q) ||
            e.location.toLowerCase().includes(q)
          : true,
      )
      .sort((a, b) => {
        if (sort === 'name') return a.name.localeCompare(b.name)
        if (sort === 'drift') return b.drift - a.drift
        if (sort === 'alerts') return b.openAlerts - a.openAlerts
        return b.riskScore - a.riskScore
      })
  }, [dept, sort, query])

  const worst = useMemo(
    () => [...employees].sort((a, b) => b.riskScore - a.riskScore)[0],
    [],
  )

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div className="mb-2">
        <h1 className="text-[20px] font-bold text-[var(--color-text)]">User Behaviour</h1>
        <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
          Understand behavioural patterns and risk levels for individual users.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Identities in scope"
          value={String(rows.length)}
          icon={<Users className="size-4" />}
          footnote={`of ${employees.length} in roster`}
        />
        <StatCard
          label="On watchlist"
          value={String(summary.watchlist)}
          delta="+2"
          icon={<ShieldAlert className="size-4" />}
          footnote="escalated this window"
        />
        <StatCard
          label="Mean drift"
          value={(employees.reduce((s, e) => s + e.drift, 0) / employees.length).toFixed(2)}
          unit="σ"
          icon={<Gauge className="size-4" />}
          footnote="vs own baseline"
        />
        <StatCard
          label="Estate watched"
          value={formatNumber(summary.monitored)}
          icon={<Users className="size-4" />}
          footnote="all directories"
        />
      </div>

      {worst && (
        <Panel
          title="Highest-risk identity"
          subtitle={`${worst.name} · ${worst.peerGroup} · ${worst.drift.toFixed(1)}σ from own baseline`}
          actions={
            <button
              type="button"
              onClick={() => onSelectEmployee(worst.id)}
              className="inline-flex items-center gap-1 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[10.5px] font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
            >
              Full profile <ChevronRight className="size-3" />
            </button>
          }
        >
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
            <div className="lg:col-span-4">
              <div className="flex items-center gap-3.5">
                <Avatar initials={worst.initials} department={worst.department} size={56} ring={riskTone(worst.riskScore).hex} />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-semibold text-[var(--color-text)]">{worst.name}</p>
                  <p className="truncate text-[11px] text-[var(--color-text-muted)]">{worst.title}</p>
                  <p className="mt-1 flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]">
                    <MapPin className="size-2.5" /> {worst.location} · {worst.department}
                  </p>
                </div>
              </div>

              <div className="mt-4 flex items-center gap-4">
                <RiskDial score={worst.riskScore} size={78} sublabel="risk" />
                <dl className="grid flex-1 grid-cols-2 gap-y-2 text-[10.5px]">
                  <div>
                    <dt className="text-[var(--color-text-faint)]">Drift</dt>
                    <dd className="num text-[var(--color-text)]">+{worst.drift.toFixed(1)}σ</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--color-text-faint)]">Detections</dt>
                    <dd className="num text-[var(--color-text)]">{alertsForEmployee(worst.id).length}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--color-text-faint)]">Last seen</dt>
                    <dd className="num text-[var(--color-text)]">{worst.lastSeen}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--color-text-faint)]">Tenure</dt>
                    <dd className="num text-[var(--color-text)]">{worst.tenureMonths} mo</dd>
                  </div>
                </dl>
              </div>

              <div className="mt-4">
                <p className="mb-1.5 text-[10px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
                  Access intensity, 24h
                </p>
                <HourStrip hourly={worst.hourly} height={38} />
              </div>
            </div>

            <div className="lg:col-span-5">
              <p className="mb-1 text-[10px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
                Behaviour vs peer group
              </p>
              <BehaviourRadar behaviour={worst.behaviour} baseline={peerBaseline(worst)} height={260} />
            </div>

            <div className="lg:col-span-3">
              <p className="mb-2 text-[10px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
                Baseline drift
              </p>
              <ul className="space-y-2">
                {worst.baselineShift.map((row) => (
                  <li key={row.label} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-[10.5px] text-[var(--color-text-muted)]">{row.label}</span>
                      <span className="num shrink-0 text-[10.5px] font-semibold text-[var(--color-critical)]">{row.delta}</span>
                    </div>
                    <p className="num mt-0.5 text-[10px] text-[var(--color-text-faint)]">
                      {row.baseline} → <span className="text-[var(--color-text)]">{row.current}</span>
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      )}

      <Panel
        title="Monitored identities"
        subtitle={`${rows.length} identities · baselines retrained 6 h ago`}
        padded={false}
        actions={
          <Segmented
            size="sm"
            value={sort}
            onChange={setSort}
            options={[
              { value: 'risk', label: 'Risk' },
              { value: 'drift', label: 'Drift' },
              { value: 'alerts', label: 'Alerts' },
              { value: 'name', label: 'Name' },
            ]}
          />
        }
      >
        <div className="flex flex-wrap items-center gap-1.5 border-b border-[var(--color-border)] px-3.5 py-3">
          <span className="mr-1.5 flex items-center gap-1 text-[10px] font-semibold tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
            <ArrowUpDown className="size-3" /> Dept
          </span>
          <Chip active={dept === 'all'} onClick={() => setDept('all')}>All</Chip>
          {departments.map((d) => (
            <Chip key={d} active={dept === d} onClick={() => setDept(d)}>{d}</Chip>
          ))}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[9.5px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">
                <th className="px-3.5 py-2.5 font-medium">Identity</th>
                <th className="px-3 py-2.5 font-medium">Peer group</th>
                <th className="px-3 py-2.5 font-medium">24h pattern</th>
                <th className="px-3 py-2.5 text-right font-medium">Drift</th>
                <th className="px-3 py-2.5 text-center font-medium">Open</th>
                <th className="px-3 py-2.5 text-right font-medium">Risk</th>
                <th className="px-3.5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {rows.map((e) => {
                const tone = riskTone(e.riskScore)
                const active = e.id === selectedEmployeeId
                return (
                  <tr
                    key={e.id}
                    onClick={() => onSelectEmployee(e.id)}
                    className={cn(
                      'group cursor-pointer transition-colors duration-150 hover:bg-[var(--color-hover)]',
                      active && 'bg-[var(--color-surface)]',
                    )}
                  >
                    <td className="px-3.5 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <Avatar
                          initials={e.initials}
                          department={e.department}
                          size={32}
                          ring={e.status === 'watchlist' ? tone.hex : undefined}
                        />
                        <div className="min-w-0">
                          <p className="flex items-center gap-1.5 truncate text-[12px] font-medium text-[var(--color-text)]">
                            {e.name}
                            {e.status === 'watchlist' && (
                              <span className="shrink-0 rounded-full bg-[var(--color-warning-bg)] px-1.5 py-px text-[8.5px] font-semibold tracking-wide text-[var(--color-warning)] uppercase ring-1 ring-[var(--color-warning-border)] ring-inset">
                                watch
                              </span>
                            )}
                          </p>
                          <p className="truncate text-[10px] text-[var(--color-text-faint)]">
                            {e.title} · {e.department}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="num px-3 py-2.5 text-[10.5px] text-[var(--color-text-muted)]">{e.peerGroup}</td>
                    <td className="w-[150px] px-3 py-2.5">
                      <HourStrip hourly={e.hourly} height={26} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span className="num text-[11px] font-medium" style={{ color: tone.hex }}>
                        +{e.drift.toFixed(1)}σ
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      {e.openAlerts > 0 ? (
                        <span className="num inline-grid size-5 place-items-center rounded-md bg-[var(--color-critical-bg)] text-[10px] font-semibold text-[var(--color-critical)] ring-1 ring-[var(--color-critical-border)] ring-inset">
                          {e.openAlerts}
                        </span>
                      ) : (
                        <span className="text-[11px] text-[var(--color-text-faint)]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end">
                        <RiskDial score={e.riskScore} size={38} stroke={3.5} />
                      </div>
                    </td>
                    <td className="px-3.5 py-2.5 text-right">
                      <ChevronRight className="ml-auto size-3.5 text-[var(--color-text-faint)] transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-[var(--color-text)]" />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {rows.length === 0 && (
          <p className="px-4 py-14 text-center text-[12px] text-[var(--color-text-faint)]">
            No identities match the current filters.
          </p>
        )}
      </Panel>
    </div>
  )
}
