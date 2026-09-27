import { ChevronRight, MapPin } from 'lucide-react'
import { riskTone } from '../../lib/utils'
import { Avatar } from '../ui/Avatar'
import { RiskDial } from '../ui/RiskDial'

/**
 * One row in the employee risk ranking.
 *
 * Deliberately not the mock `Employee` domain type. That type carries a
 * 24-slot hourly activity strip and a peer-drift figure in standard
 * deviations, neither of which any endpoint produces — rendering them for a
 * real employee would mean drawing an empty strip and a drift of zero where a
 * figure is expected, which reads as "this person is unremarkable" rather than
 * "this was never measured". `riskChange` is the number the risk engine
 * actually records: how far the score moved.
 */
export interface RiskRowData {
  id: string
  name: string
  initials: string
  /** Organisational department, display-only. */
  department?: string | null
  jobTitle?: string | null
  branchName?: string | null
  riskScore: number
  riskLevel: string
  riskChange: number
  openAlerts: number
}

export function IdentityRow({ employee, rank, onOpen }: {
  employee: RiskRowData
  rank?: number
  onOpen: (id: string) => void
}) {
  const tone = riskTone(employee.riskScore)
  const watching = employee.openAlerts > 0

  return (
    <button
      type="button"
      onClick={() => onOpen(employee.id)}
      className="group flex w-full items-center gap-3 border-b border-[var(--color-border)] px-3.5 py-2.5 text-left transition-colors duration-150 last:border-0 hover:bg-[var(--color-hover)]"
    >
      {rank !== undefined && (
        <span className="num w-4 shrink-0 text-[11px] text-[var(--color-text-faint)]">{rank}</span>
      )}

      <Avatar initials={employee.initials} size={34} ring={watching ? tone.hex : undefined} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[12px] font-medium text-[var(--color-text)]">{employee.name}</span>
          {watching && (
            <span className="shrink-0 rounded-full bg-[var(--color-warning-bg)] px-1.5 py-px text-[9px] font-semibold tracking-wide text-[var(--color-warning)] uppercase ring-1 ring-[var(--color-warning-border)] ring-inset">
              {employee.openAlerts} open
            </span>
          )}
        </div>
        <p className="mt-0.5 flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
          <span className="truncate">{employee.jobTitle ?? employee.riskLevel}</span>
          {employee.branchName && (
            <span className="hidden items-center gap-1 sm:flex">
              <MapPin className="size-2.5" />
              {employee.branchName}
            </span>
          )}
        </p>
      </div>

      <div className="w-[46px] shrink-0 text-right">
        <span className="num text-[11px] font-medium" style={{ color: tone.hex }}>
          {employee.riskChange > 0 ? '+' : ''}{employee.riskChange.toFixed(1)}
        </span>
        <p className="mt-0.5 text-[9px] text-[var(--color-text-faint)]">change</p>
      </div>

      <RiskDial score={employee.riskScore} size={44} stroke={4} />

      <ChevronRight
        className="size-3.5 shrink-0 text-[var(--color-text-faint)] transition-transform duration-150 group-hover:translate-x-0.5 group-hover:text-[var(--color-text)]"
      />
    </button>
  )
}
