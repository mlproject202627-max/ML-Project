import { BrainCircuit, Cpu, Gauge, RefreshCw, TriangleAlert, Zap } from 'lucide-react'
import { departmentBreakdown, detectors } from '../../data/mock'
import type { DetectorHealth } from '../../data/types'
import { cn, formatNumber } from '../../lib/utils'
import { Meter } from '../ui/Meter'
import { Panel } from '../ui/Panel'
import { StatCard } from '../ui/StatCard'
import { Tag } from '../ui/Badge'
import { DeptBars } from '../charts/DeptBars'

const STATUS_STYLE: Record<DetectorHealth['status'], { label: string; className: string; hex: string }> = {
  healthy: { label: 'Healthy', className: 'text-[#a3a3a3] bg-white/[0.04] ring-white/10', hex: '#a3a3a3' },
  degraded: { label: 'Degraded', className: 'text-[#fde68a] bg-[#fde68a]/10 ring-[#fde68a]/25', hex: '#fde68a' },
  training: { label: 'Retraining', className: 'text-white bg-white/[0.06] ring-white/15', hex: '#ffffff' },
}

const TOP_FEATURES = [
  { name: 'off_hours_offset_hrs', weight: 0.142, family: 'temporal' },
  { name: 'peer_group_centroid_dist', weight: 0.128, family: 'peer' },
  { name: 'distinct_share_breadth', weight: 0.113, family: 'access' },
  { name: 'privilege_grant_delta_7d', weight: 0.097, family: 'entitlement' },
  { name: 'session_geo_velocity', weight: 0.089, family: 'session' },
  { name: 'export_bytes_per_session', weight: 0.081, family: 'volume' },
  { name: 'new_host_contact_rate', weight: 0.074, family: 'graph' },
  { name: 'auth_failure_ratio', weight: 0.061, family: 'auth' },
  { name: 'dormancy_days_since_auth', weight: 0.052, family: 'temporal' },
  { name: 'device_fingerprint_novelty', weight: 0.044, family: 'device' },
]

function MetricBar({ label, value, color, suffix = '' }: {
  label: string
  value: number
  color: string
  suffix?: string
}) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-[9.5px] tracking-[0.08em] text-faint uppercase">{label}</span>
        <span className="num text-[10.5px] font-medium" style={{ color }}>
          {value.toFixed(value < 1 ? 3 : 1)}{suffix}
        </span>
      </div>
      <Meter value={value <= 1 ? value * 100 : value} color={color} height={3} />
    </div>
  )
}

export function Models() {
  const healthy = detectors.filter((d) => d.status === 'healthy').length
  const degraded = detectors.filter((d) => d.status === 'degraded').length
  const training = detectors.filter((d) => d.status === 'training').length
  const ensembleAuc = detectors.reduce((s, d) => s + d.auc, 0) / detectors.length
  const maxWeight = Math.max(...TOP_FEATURES.map((f) => f.weight))

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Detectors deployed" value={String(detectors.length)} icon={<BrainCircuit className="size-4" />} footnote={`${healthy} healthy · ${degraded} degraded · ${training} retraining`} />
        <StatCard label="Ensemble AUC" value={ensembleAuc.toFixed(3)} delta="+0.011" deltaGood icon={<Gauge className="size-4" />} footnote="mean across fleet" />
        <StatCard label="Features scored" value={formatNumber(detectors.reduce((s, d) => s + d.features, 0))} icon={<Cpu className="size-4" />} footnote="union of all detectors" />
        <StatCard label="Ingest throughput" value="195k" unit="ev/s" delta="+8.4%" deltaGood icon={<Zap className="size-4" />} footnote="aggregate pipeline" />
      </div>

      {degraded > 0 && (
        <div className="panel flex items-start gap-3 border-[#fde68a]/30 bg-[#fde68a]/[0.05] p-3.5">
          <TriangleAlert className="mt-px size-4 shrink-0 text-[#fde68a]" />
          <div className="min-w-0">
            <p className="text-[12px] font-semibold text-[#fde68a]">
              {degraded} detector{degraded > 1 ? 's' : ''} exceeding drift tolerance
            </p>
            <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted">
              Input distribution shift above 0.20 KL divergence. Access Sequence Transformer is
              scheduled for retraining on the refreshed peer baselines; until then its weight in
              the ensemble is down-weighted by 35%.
            </p>
          </div>
          <button
            type="button"
            className="ml-auto inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-[#fde68a]/40 bg-[#fde68a]/12 px-2.5 py-1.5 text-[10.5px] font-semibold text-[#fde68a] transition-colors duration-150 hover:border-[#fde68a]/60 hover:bg-[#fde68a]/20"
          >
            <RefreshCw className="size-3" /> Retrain now
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {detectors.map((d) => {
          const status = STATUS_STYLE[d.status]
          return (
            <Panel
              key={d.name}
              title={d.name}
              subtitle={d.family}
              actions={
                <span className={cn('rounded-md px-2 py-0.5 text-[9.5px] font-semibold tracking-wide uppercase ring-1 ring-inset', status.className)}>
                  {status.label}
                </span>
              }
            >
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                  <MetricBar label="Precision" value={d.precision} color="#a3a3a3" />
                  <MetricBar label="Recall" value={d.recall} color="#a3a3a3" />
                  <MetricBar label="F1" value={d.f1} color="#a3a3a3" />
                  <MetricBar label="ROC AUC" value={d.auc} color="#a3a3a3" />
                </div>

                <div className="border-t border-line-soft pt-3">
                  <div className="mb-1.5 flex items-baseline justify-between">
                    <span className="text-[9.5px] tracking-[0.08em] text-faint uppercase">Distribution drift</span>
                    <span className={cn('num text-[10.5px] font-medium', d.drift > 0.2 ? 'text-[#fda4af]' : d.drift > 0.1 ? 'text-[#fde68a]' : 'text-[#a3a3a3]')}>
                      {d.drift.toFixed(2)} KL
                    </span>
                  </div>
                  <Meter value={Math.min(100, (d.drift / 0.3) * 100)} color={d.drift > 0.2 ? '#fda4af' : d.drift > 0.1 ? '#fde68a' : '#a3a3a3'} height={3} />
                </div>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  <Tag>{formatNumber(d.features)} features</Tag>
                  <Tag>{d.throughput}</Tag>
                  <Tag>trained {d.lastTrained}</Tag>
                </div>
              </div>
            </Panel>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel className="xl:col-span-7" title="Global feature attribution" subtitle="Mean absolute contribution to the ensemble anomaly score" padded={false}>
          <ul className="divide-y divide-line-soft">
            {TOP_FEATURES.map((f) => (
              <li key={f.name} className="flex items-center gap-3.5 px-3.5 py-2.5 transition-colors duration-150 hover:bg-surface-2">
                <span className="num w-[220px] shrink-0 truncate text-[11px] text-fg">{f.name}</span>
                <Tag className="hidden shrink-0 sm:inline-flex">{f.family}</Tag>
                <Meter value={(f.weight / maxWeight) * 100} color="#666666" height={5} className="flex-1" />
                <span className="num w-11 shrink-0 text-right text-[11px] font-medium text-muted">{f.weight.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Estate risk distribution" subtitle="Mean composite score by department">
            <DeptBars data={departmentBreakdown} />
          </Panel>

          <Panel title="Training cadence" subtitle="Baseline refresh schedule">
            <ul className="space-y-3">
              {[
                { label: 'Peer baselines', value: 92, detail: 'every 6 hours' },
                { label: 'Behavioural autoencoder', value: 74, detail: 'nightly at 02:00 UTC' },
                { label: 'Sequence transformer', value: 41, detail: 'weekly, Sunday' },
                { label: 'Entitlement graph rebuild', value: 88, detail: 'every 4 hours' },
              ].map((row) => (
                <li key={row.label}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <span className="text-[11px] text-fg">{row.label}</span>
                    <span className="num text-[10px] text-faint">{row.detail}</span>
                  </div>
                  <Meter value={row.value} color="#666666" height={4} />
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}
