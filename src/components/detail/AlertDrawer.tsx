import { Building2, Clock, Globe, MapPin, Server, User } from 'lucide-react'
import { employeeById } from '../../data/mock'
import { Drawer } from '../ui/Drawer'
import { Avatar } from '../ui/Avatar'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { RiskDial } from '../ui/RiskDial'
import { FactorBars } from '../charts/FactorBars'
import { relativeTime } from '../../lib/utils'

export function AlertDrawer({ alertId, onClose, onOpenEmployee }: {
  alertId: string | null
  onClose: () => void
  onOpenEmployee: (id: string) => void
}) {
  const alert = alertId ? alerts.find((a) => a.id === alertId) : undefined
  const emp = alert ? employeeById(alert.employeeId) : undefined

  return (
    <Drawer open={Boolean(alertId)} onClose={onClose} width={520} title="">
      {!alert ? (
        <span />
      ) : (
        <div className="space-y-5">
          {/* Header */}
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={alert.severity} />
                <StatusBadge status={alert.status} />
                <span className="num text-[11px] text-[var(--color-text-faint)]">{alert.id}</span>
              </div>
              <h3 className="mt-2 text-[15px] font-semibold text-[var(--color-text)]">{alert.headline}</h3>
              <p className="mt-1 text-[12px] leading-relaxed text-[var(--color-text-muted)]">{alert.narrative}</p>
            </div>
            <RiskDial score={alert.riskScore} size={72} sublabel="risk" />
          </div>

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3">
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <User className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Identity</span>
              </div>
              {emp && (
                <button type="button" onClick={() => onOpenEmployee(emp.id)} className="mt-1.5 flex items-center gap-2 text-left">
                  <Avatar initials={emp.initials} department={emp.department} size={28} />
                  <span className="text-[12px] font-medium text-[var(--color-text)] hover:underline">{emp.name}</span>
                </button>
              )}
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Globe className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Location</span>
              </div>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--color-text)]">{emp?.location || 'Unknown'}</p>
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Server className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Asset</span>
              </div>
              <p className="mt-1.5 truncate text-[12px] font-medium text-[var(--color-text)]">{alert.asset}</p>
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Clock className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Detected</span>
              </div>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--color-text)]">{relativeTime(alert.detectedAt)}</p>
            </div>
          </div>

          {/* Factors */}
          <div>
            <h4 className="mb-2 text-[12px] font-semibold text-[var(--color-text)]">Contributing Factors</h4>
            <FactorBars factors={alert.factors} />
          </div>

          {/* Source */}
          <div className="card p-3">
            <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
              <Building2 className="size-3.5" />
              Detector: {alert.detector}
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
              <MapPin className="size-3.5" />
              Source IP: {alert.sourceIp} · {alert.geo}
            </div>
          </div>
        </div>
      )}
    </Drawer>
  )
}

import { alerts } from '../../data/mock'
