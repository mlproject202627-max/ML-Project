import { ShieldCheck } from 'lucide-react'
import { Meter } from '../ui/Meter'
import { riskLevel, riskTone } from '../../lib/utils'
import { getAdminDashboard } from '../../lib/adminApi'
import { useApiResource } from '../../lib/useApi'

/**
 * Estate posture, from live figures only.
 *
 * This widget previously rendered a hardcoded `72` with the label "elevated"
 * and two invented percentages underneath it. It sits in the sidebar of every
 * screen in the console, so those numbers were the most-seen thing in the
 * product and the least connected to anything real.
 *
 * The score is now the mean composite risk across monitored employees — the
 * one estate-wide aggregate the risk engine actually produces. Coverage and
 * false-positive rate had no backing endpoint at all and are not reproducible
 * from the data, so rather than restate them the panel shows two counts it can
 * stand behind.
 */
export function PostureWidget() {
  const { data, error } = useApiResource(() => getAdminDashboard(), [])

  if (error || !data) {
    return (
      <div className="rounded-lg border border-line bg-surface-2 p-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold tracking-[0.13em] text-faint uppercase">
            Posture
          </span>
          <ShieldCheck className="size-3.5 text-white/60" />
        </div>
        <p className="mt-2 text-[10px] text-faint">
          {error ? 'Unavailable.' : 'Loading…'}
        </p>
      </div>
    )
  }

  const ranking = data.charts.employeeRiskRanking
  const score = ranking.length
    ? Math.round(ranking.reduce((sum, r) => sum + r.riskScore, 0) / ranking.length)
    : 0
  const tone = riskTone(score)

  return (
    <div className="rounded-lg border border-line bg-surface-2 p-3">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-semibold tracking-[0.13em] text-faint uppercase">
          Posture
        </span>
        <ShieldCheck className="size-3.5 text-white/60" />
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="num text-[20px] leading-none font-semibold text-white">{score}</span>
        <span className="text-[10px] text-faint">/100 mean</span>
        <span className="num ml-auto text-[10px]" style={{ color: tone.hex }}>
          {riskLevel(score).toLowerCase()}
        </span>
      </div>
      <Meter value={score} color={tone.hex} height={4} className="mt-2.5" />
      <dl className="mt-2.5 grid grid-cols-2 gap-x-2 gap-y-1.5 text-[10px]">
        <div>
          <dt className="text-faint">Monitored</dt>
          <dd className="num text-fg">{data.cards.employeesMonitored}</dd>
        </div>
        <div>
          <dt className="text-faint">Critical</dt>
          <dd className="num text-fg">{data.cards.criticalAlerts}</dd>
        </div>
      </dl>
    </div>
  )
}
