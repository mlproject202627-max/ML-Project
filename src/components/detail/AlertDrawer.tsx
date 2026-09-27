import { useMemo, useState } from 'react'
import {
  Building2, Clock, Globe, Loader2, MapPin, MessageSquarePlus,
  Scale, Server, ShieldAlert, ShieldCheck, User,
} from 'lucide-react'
import { Drawer } from '../ui/Drawer'
import { Avatar } from '../ui/Avatar'
import { SeverityBadge, StatusBadge } from '../ui/Badge'
import { RiskDial } from '../ui/RiskDial'
import { FactorBars } from '../charts/FactorBars'
import { ErrorState } from '../ui/ErrorState'
import { LoadingState } from '../ui/LoadingState'
import { relativeTime } from '../../lib/utils'
import { useApiResource } from '../../lib/useApi'
import { addAlertNote, getAlertDetail, resolveAlert, startInvestigation } from '../../lib/adminApi'
import type { AlertDetail } from '../../lib/adminApi'
import { alertFromApi, enrichmentFromDetail } from '../../lib/adapters'
import { useAuth } from '../../lib/auth'

/**
 * Roles the server admits to the write endpoints (`require_security_analyst`).
 * A VIEWER can read every screen in this console and change nothing.
 *
 * Hiding these controls from a VIEWER is a courtesy, not the control. The
 * control is the 403 FastAPI returns regardless of what the browser rendered —
 * which is also why `actionError` below surfaces a refusal rather than
 * swallowing it.
 */
const WRITE_ROLES = ['ADMIN', 'SECURITY_MANAGER', 'SECURITY_ANALYST']

type Pending = null | 'investigate' | 'note' | 'resolve' | 'false-positive'

export function AlertDrawer({ alertId, onClose, onOpenEmployee }: {
  alertId: string | null
  onClose: () => void
  onOpenEmployee: (id: string) => void
}) {
  const { user } = useAuth()
  const canAct = WRITE_ROLES.includes(user?.role ?? '')

  const { data, error, loading, reload } = useApiResource<AlertDetail | null>(
    () => (alertId ? getAlertDetail(alertId) : Promise.resolve(null)),
    [alertId],
  )

  const alert = useMemo(() => (data ? alertFromApi(data.alert) : null), [data])
  const enrichment = useMemo(() => (data ? enrichmentFromDetail(data) : null), [data])

  const [note, setNote] = useState('')
  const [reason, setReason] = useState('')
  const [pending, setPending] = useState<Pending>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const employee = data?.employee as { id?: string; name?: string; department?: string | null; branchName?: string | null } | undefined

  async function run(kind: Pending, call: () => Promise<unknown>) {
    setPending(kind)
    setActionError(null)
    try {
      await call()
      reload()
    } catch (cause) {
      // A 409 here is the server telling the analyst the case already moved —
      // useful information, not an error to hide.
      setActionError(cause instanceof Error ? cause.message : 'The action was refused.')
    } finally {
      setPending(null)
    }
  }

  const busy = pending !== null
  const isOpen = alert?.status === 'new' || alert?.status === 'investigating'

  return (
    <Drawer open={Boolean(alertId)} onClose={onClose} width={520} title="">
      {loading ? (
        <div className="p-1">
          <LoadingState rows={4} />
        </div>
      ) : error ? (
        <ErrorState title="Could not open this alert" description={error} onRetry={reload} />
      ) : !alert || !enrichment ? (
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
              {alert.employeeName && (
                <button
                  type="button"
                  onClick={() => employee?.id && onOpenEmployee(employee.id)}
                  className="mt-1.5 flex items-center gap-2 text-left"
                >
                  <Avatar initials={alert.employeeInitials ?? '??'} size={28} />
                  <span className="text-[12px] font-medium text-[var(--color-text)] hover:underline">
                    {alert.employeeName}
                  </span>
                </button>
              )}
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Globe className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Location</span>
              </div>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--color-text)]">
                {enrichment.geo || 'Unknown'}
              </p>
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Server className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Trigger</span>
              </div>
              <p className="mt-1.5 truncate text-[12px] font-medium text-[var(--color-text)]">
                {alert.asset || '—'}
              </p>
            </div>
            <div className="card p-3">
              <div className="flex items-center gap-2">
                <Clock className="size-3.5 text-[var(--color-text-faint)]" />
                <span className="text-[10px] text-[var(--color-text-faint)]">Detected</span>
              </div>
              <p className="mt-1.5 text-[12px] font-medium text-[var(--color-text)]">
                {relativeTime(alert.detectedAt)}
              </p>
            </div>
          </div>

          {/* Why it fired — the real rule names, not a UI grouping */}
          <div>
            <h4 className="mb-2 text-[12px] font-semibold text-[var(--color-text)]">Contributing Factors</h4>
            {enrichment.factors.length === 0 ? (
              <p className="card p-3 text-[11.5px] text-[var(--color-text-muted)]">
                This detection carries no rule hits — it was raised on statistical
                evidence alone.
              </p>
            ) : (
              <>
                <FactorBars factors={enrichment.factors} />
                <ul className="mt-3 space-y-1.5">
                  {enrichment.ruleHits.map((h) => (
                    <li key={h.ruleId} className="flex gap-2 text-[11.5px] leading-relaxed">
                      <span className="num shrink-0 font-medium text-[var(--color-text-muted)]">{h.ruleId}</span>
                      <span className="text-[var(--color-text-secondary)]">{h.explanation}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          {/* Investigation */}
          <div className="card p-3.5">
            <div className="flex items-center gap-2">
              <ShieldAlert className="size-3.5 text-[var(--color-text-faint)]" />
              <h4 className="text-[12px] font-semibold text-[var(--color-text)]">Investigation</h4>
            </div>

            {!canAct && (
              <p className="mt-2 text-[11.5px] text-[var(--color-text-muted)]">
                Your role has read-only access to the console. An analyst can
                action this case.
              </p>
            )}

            {canAct && !isOpen && (
              <p className="mt-2 text-[11.5px] text-[var(--color-text-muted)]">
                This case is closed. Its history is preserved below and cannot be
                edited.
              </p>
            )}

            {canAct && isOpen && (
              <div className="mt-3 space-y-3">
                <div>
                  <label htmlFor="alert-note" className="text-[10px] tracking-[0.08em] text-[var(--color-text-faint)] uppercase">
                    Investigator note
                  </label>
                  <textarea
                    id="alert-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={2}
                    placeholder="What did you check?"
                    className="mt-1 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-border-strong)]"
                  />
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy || note.trim().length === 0}
                      onClick={() => run('note', () => addAlertNote(alert.id, note.trim()))}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover)] disabled:opacity-40"
                    >
                      {pending === 'note' ? <Loader2 className="size-3 animate-spin" /> : <MessageSquarePlus className="size-3" />}
                      Add note
                    </button>
                    {alert.status === 'new' && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => run('investigate', () => startInvestigation(alert.id))}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover)] disabled:opacity-40"
                      >
                        {pending === 'investigate' ? <Loader2 className="size-3 animate-spin" /> : <ShieldCheck className="size-3" />}
                        Start investigation
                      </button>
                    )}
                  </div>
                </div>

                <div className="border-t border-[var(--color-border)] pt-3">
                  <label htmlFor="alert-reason" className="text-[10px] tracking-[0.08em] text-[var(--color-text-faint)] uppercase">
                    Resolution reason (required)
                  </label>
                  <textarea
                    id="alert-reason"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    rows={2}
                    placeholder="Why is this case being closed?"
                    className="mt-1 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-border-strong)]"
                  />
                  <div className="mt-2 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy || reason.trim().length < 3}
                      onClick={() => run('resolve', () => resolveAlert(alert.id, reason.trim(), 'RESOLVED'))}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)] disabled:opacity-40"
                    >
                      {pending === 'resolve' ? <Loader2 className="size-3 animate-spin" /> : <ShieldCheck className="size-3" />}
                      Resolve
                    </button>
                    <button
                      type="button"
                      disabled={busy || reason.trim().length < 3}
                      onClick={() => run('false-positive', () => resolveAlert(alert.id, reason.trim(), 'FALSE_POSITIVE'))}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover)] disabled:opacity-40"
                    >
                      {pending === 'false-positive' ? <Loader2 className="size-3 animate-spin" /> : <Scale className="size-3" />}
                      Mark false positive
                    </button>
                  </div>
                </div>

                {actionError && (
                  <p className="text-[11.5px] text-[var(--color-critical)]">{actionError}</p>
                )}
              </div>
            )}

            {/* Case history — appended to, never rewritten */}
            {data && data.actions.length > 0 && (
              <ul className="mt-3 space-y-2 border-t border-[var(--color-border)] pt-3">
                {data.actions.map((a) => (
                  <li key={a.id} className="text-[11.5px] leading-relaxed">
                    <span className="text-[var(--color-text-muted)]">
                      {a.createdAt ? relativeTime(a.createdAt) : ''}
                      {a.adminCode ? ` · ${a.adminCode}` : ''}
                    </span>
                    <span className="ml-1.5 font-medium text-[var(--color-text-secondary)]">
                      {a.action.replace(/_/g, ' ').toLowerCase()}
                    </span>
                    {a.note && <p className="text-[var(--color-text-muted)]">{a.note}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Source */}
          <div className="card p-3">
            <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
              <Building2 className="size-3.5" />
              Detector: {enrichment.detector}
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-[10px] text-[var(--color-text-faint)]">
              <MapPin className="size-3.5" />
              Source IP: {enrichment.sourceIp || 'not recorded'}
              {enrichment.geo ? ` · ${enrichment.geo}` : ''}
            </div>
            {alert.status === 'contained' || alert.status === 'dismissed' ? (
              <div className="mt-1.5 text-[10px] text-[var(--color-text-faint)]">
                Closed {data?.alert.resolvedAt ? relativeTime(data.alert.resolvedAt) : ''}
                {data?.alert.resolutionReason ? ` — ${data.alert.resolutionReason}` : ''}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </Drawer>
  )
}
