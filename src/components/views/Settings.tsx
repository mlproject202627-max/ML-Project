import { useCallback, useEffect, useState } from 'react'
import { Bell, Database, Fingerprint, KeyRound, ShieldCheck, Sliders, Trash2, UserPlus } from 'lucide-react'
import { detectors, employees } from '../../data/mock'
import { Avatar } from '../ui/Avatar'
import { Panel } from '../ui/Panel'
import { Segmented } from '../ui/Segmented'
import { Slider, Toggle } from '../ui/Controls'
import { riskTone } from '../../lib/utils'
import { useAuth } from '../../lib/auth'
import {
  adminCreateUser, adminDeactivateUser, adminUpdateUser, getTelemetry, createAgentKey,
  listAgentKeys, revokeAgentKey, getUsers, getRoleMeta,
  type ApiAdminUser, type ApiTelemetryEvent, type RoleMeta,
} from '../../lib/api'

/** Roles that may open the staff directory (mirrors backend STAFF_VIEW_ROLES). */
const STAFF_VIEW_ROLES = ['ADMIN', 'SECURITY_MANAGER', 'SECURITY_ANALYST', 'BRANCH_MANAGER', 'OPERATIONS_MANAGER', 'COMPLIANCE_OFFICER']

const BANKING_ROLES = ['TELLER', 'RELATIONSHIP_MANAGER', 'BRANCH_MANAGER', 'COMPLIANCE_OFFICER', 'OPERATIONS_MANAGER']
const PLATFORM_ROLES = ['ADMIN', 'SECURITY_MANAGER', 'SECURITY_ANALYST', 'VIEWER']

const ROLE_LABELS: Record<string, string> = {
  ADMIN: 'Administrator',
  SECURITY_MANAGER: 'Security Manager',
  SECURITY_ANALYST: 'Security Analyst',
  VIEWER: 'Viewer',
  TELLER: 'Teller',
  RELATIONSHIP_MANAGER: 'Relationship Manager',
  BRANCH_MANAGER: 'Branch Manager',
  COMPLIANCE_OFFICER: 'Compliance Officer',
  OPERATIONS_MANAGER: 'Operations Manager',
}

type ManagedUser = ApiAdminUser

function UserManagementPanel({ canManage }: { canManage: boolean }) {
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [meta, setMeta] = useState<RoleMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [successNote, setSuccessNote] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '', email: '', password: '', role: 'RELATIONSHIP_MANAGER',
    department: '', jobTitle: '', employeeCode: '', branchCode: '', mfaEnabled: true,
  })
  const [submitting, setSubmitting] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [res, roleMeta] = await Promise.all([getUsers({ page: 1, page_size: 100 }), getRoleMeta()])
      setUsers(res.items as ManagedUser[])
      setMeta(roleMeta)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    setSuccessNote(null)
    try {
      const branch = meta?.branches.find((b) => b.code === form.branchCode)
      const created = await adminCreateUser({
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role,
        department: form.department || undefined,
        jobTitle: form.jobTitle || undefined,
        employeeCode: form.employeeCode || undefined,
        branchCode: form.branchCode || undefined,
        branchName: branch?.name,
        mfaEnabled: form.mfaEnabled,
      })
      setSuccessNote(`${created.name} added as ${ROLE_LABELS[created.roles[0]?.name ?? ''] ?? form.role}${created.employee_code ? ` (${created.employee_code})` : ''}. They can sign in with the temporary password.`)
      setForm({ name: '', email: '', password: '', role: 'RELATIONSHIP_MANAGER', department: '', jobTitle: '', employeeCode: '', branchCode: form.branchCode, mfaEnabled: true })
      setShowForm(false)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create user')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStatus = async (u: ManagedUser, status: string) => {
    try {
      await adminUpdateUser(u.id, { status })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update user')
    }
  }

  const handleRole = async (u: ManagedUser, role: string) => {
    try {
      await adminUpdateUser(u.id, { role })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role')
    }
  }

  const handleDeactivate = async (u: ManagedUser) => {
    try {
      await adminDeactivateUser(u.id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to deactivate user')
    }
  }

  return (
    <Panel
      title="Employee directory"
      subtitle={canManage ? 'Banking staff and platform users — add employees and assign roles' : 'Staff directory (read-only)'}
      actions={<UserPlus className="size-3.5 text-[var(--color-text-faint)]" />}
    >
      {error && <p className="mb-3 rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11px] text-[var(--color-critical)]">{error}</p>}
      {successNote && <p className="mb-3 rounded-lg border border-[var(--color-success-border)] bg-[var(--color-success-bg)] px-3 py-2 text-[11px] text-[var(--color-success)]">{successNote}</p>}

      {canManage && showForm && (
        <form onSubmit={handleCreate} className="mb-4 grid grid-cols-1 gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 sm:grid-cols-2">
          <input required placeholder="Full name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
          <input required type="email" placeholder="Work email *" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className={inputCls} />
          <input required type="password" minLength={8} placeholder="Temporary password (min 8 chars) *" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputCls} />
          <input placeholder="Job title (e.g. Senior Teller)" value={form.jobTitle} onChange={(e) => setForm({ ...form, jobTitle: e.target.value })} className={inputCls} />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className={inputCls} title="Role">
            <optgroup label="Banking roles">
              {BANKING_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </optgroup>
            <optgroup label="Platform roles">
              {PLATFORM_ROLES.filter((r) => r !== 'ADMIN').map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
            </optgroup>
          </select>
          <select value={form.branchCode} onChange={(e) => setForm({ ...form, branchCode: e.target.value })} className={inputCls} title="Branch">
            <option value="">Branch (optional)</option>
            {(meta?.branches ?? []).map((b) => <option key={b.code} value={b.code}>{b.name}</option>)}
          </select>
          <input placeholder="Department (optional)" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className={inputCls} />
          <input placeholder="Employee ID (auto if blank, e.g. EMP-10452)" value={form.employeeCode} onChange={(e) => setForm({ ...form, employeeCode: e.target.value })} className={inputCls} />
          <label className="flex items-center gap-2 text-[11.5px] text-[var(--color-text-muted)]">
            <input type="checkbox" checked={form.mfaEnabled} onChange={(e) => setForm({ ...form, mfaEnabled: e.target.checked })} className="size-3.5 accent-[var(--color-primary)]" />
            MFA enabled for this employee
          </label>
          <div className="flex items-center gap-2 sm:col-span-2">
            <button type="submit" disabled={submitting} className="h-9 flex-1 rounded-lg bg-[var(--color-primary)] px-3 text-[11.5px] font-semibold text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)] disabled:opacity-40">{submitting ? 'Adding…' : 'Add employee'}</button>
            <button type="button" onClick={() => setShowForm(false)} className="h-9 rounded-lg border border-[var(--color-border)] px-3 text-[11.5px] text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)]">Cancel</button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="py-8 text-center text-[12px] text-[var(--color-text-faint)]">Loading users…</p>
      ) : users.length === 0 ? (
        <p className="py-8 text-center text-[12px] text-[var(--color-text-faint)]">No users yet — create the first one.</p>
      ) : (
        <ul className="divide-y divide-[var(--color-border)]">
          {users.map((u) => {
            const role = u.roles[0]?.name ?? u.role ?? 'VIEWER'
            return (
              <li key={u.id} className="flex flex-wrap items-center gap-3 py-2.5">
                <Avatar initials={u.name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase()} department={'IT Ops' as const} size={32} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12px] font-medium text-[var(--color-text)]">
                    {u.name}
                    {u.employee_code && <span className="num ml-1.5 text-[10px] font-normal text-[var(--color-text-faint)]">{u.employee_code}</span>}
                    <span className="ml-1.5 text-[10px] font-normal text-[var(--color-text-faint)]">{u.email}</span>
                  </p>
                  <p className="text-[10px] text-[var(--color-text-faint)]">
                    {u.jobTitle ?? '—'}{u.branch_name ? ` · ${u.branch_name}` : ''}{u.department ? ` · ${u.department}` : ''} · last login {u.last_login ? new Date(u.last_login).toLocaleString() : 'never'}
                  </p>
                </div>
                {canManage ? (
                  <>
                    <select
                      value={role}
                      onChange={(e) => void handleRole(u, e.target.value)}
                      className="h-7 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 text-[10.5px] text-[var(--color-text-muted)] outline-none"
                      title="Change role"
                    >
                      {[...BANKING_ROLES, ...PLATFORM_ROLES].map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
                    </select>
                    <select
                      value={u.status ?? 'ACTIVE'}
                      onChange={(e) => void handleStatus(u, e.target.value)}
                      className="h-7 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-1.5 text-[10.5px] text-[var(--color-text-muted)] outline-none"
                      title="Change status"
                    >
                      <option>ACTIVE</option>
                      <option>SUSPENDED</option>
                      <option>DISABLED</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleDeactivate(u)}
                      title={`Deactivate ${u.name}`}
                      className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-text-faint)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </>
                ) : (
                  <span className="rounded-md border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-text-muted)]">{ROLE_LABELS[role] ?? role}</span>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-3 border-t border-[var(--color-border)] pt-3">
        {canManage && !showForm && (
          <button type="button" onClick={() => setShowForm(true)} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-[10.5px] font-medium text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]">
            + Add employee
          </button>
        )}
      </div>
    </Panel>
  )
}

function AgentKeysPanel() {
  const [keys, setKeys] = useState<Array<{ id: string; label?: string | null; user_id: string; active: boolean; last_used_at?: string | null; created_at: string }>>([])
  const [users, setUsers] = useState<ManagedUser[]>([])
  const [newKey, setNewKey] = useState<string | null>(null)
  const [form, setForm] = useState({ label: '', userId: '' })
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setKeys(await listAgentKeys())
      const res = await getUsers({ page: 1, page_size: 100 })
      setUsers(res.items as ManagedUser[])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load agent keys')
    }
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const created = await createAgentKey({ label: form.label, userId: form.userId })
      setNewKey(created.key) // shown exactly once
      setForm({ label: '', userId: '' })
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create agent key')
    }
  }

  const handleRevoke = async (id: string) => {
    try {
      await revokeAgentKey(id)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to revoke key')
    }
  }

  return (
    <Panel
      title="Endpoint agents"
      subtitle="Issue keys so machines can report real USB & file activity"
      actions={<KeyRound className="size-3.5 text-[var(--color-text-faint)]" />}
    >
      {error && <p className="mb-3 rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11px] text-[var(--color-critical)]">{error}</p>}

      {newKey && (
        <div className="mb-3 rounded-lg border border-[var(--color-warning-border)] bg-[var(--color-warning-bg)] p-3">
          <p className="text-[10.5px] font-semibold text-[var(--color-warning)]">Copy this key now — it will not be shown again</p>
          <code className="mt-1 block overflow-x-auto rounded bg-[var(--color-card)] px-2 py-1.5 text-[11px] text-[var(--color-text)] num">{newKey}</code>
        </div>
      )}

      <form onSubmit={handleCreate} className="mb-3 flex flex-wrap items-center gap-2">
        <input required placeholder="Label (e.g. Omar's workstation)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="h-9 min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-[12px] text-[var(--color-text)] outline-none focus:border-[var(--color-border-strong)]" />
        <select required value={form.userId} onChange={(e) => setForm({ ...form, userId: e.target.value })} className="h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-[12px] text-[var(--color-text)] outline-none">
          <option value="">Monitored user…</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
        <button type="submit" className="h-9 rounded-lg bg-[var(--color-primary)] px-3 text-[11.5px] font-semibold text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)]">Issue key</button>
      </form>

      {keys.length === 0 ? (
        <p className="py-6 text-center text-[11px] text-[var(--color-text-faint)]">No agent keys issued yet.</p>
      ) : (
        <ul className="divide-y divide-[var(--color-border)]">
          {keys.map((k) => (
            <li key={k.id} className="flex items-center gap-3 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11.5px] text-[var(--color-text)]">{k.label ?? 'Unnamed agent'}</p>
                <p className="text-[9.5px] text-[var(--color-text-faint)]">user {k.user_id.slice(0, 8)}… · {k.active ? 'active' : 'revoked'} · last used {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : 'never'}</p>
              </div>
              {k.active && (
                <button type="button" onClick={() => void handleRevoke(k.id)} className="rounded-lg border border-[var(--color-border)] px-2 py-1 text-[10px] text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]">Revoke</button>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 border-t border-[var(--color-border)] pt-3 text-[10px] leading-relaxed text-[var(--color-text-faint)]">
        Run the agent on the user's machine:<br />
        <code className="num">backend/agent/sentinel_agent.py --api &lt;url&gt; --key &lt;key&gt;</code>
      </p>
    </Panel>
  )
}

function RecentTelemetryPanel() {
  const [events, setEvents] = useState<ApiTelemetryEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getTelemetry({ page: 1, page_size: 12 })
      .then((rows) => { if (!cancelled) setEvents(rows) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load telemetry') })
    return () => { cancelled = true }
  }, [])

  const typeTone: Record<string, string> = {
    LOGIN_TIME: 'var(--color-info)',
    LOGOUT_TIME: 'var(--color-info)',
    LOCATION_UPDATE: 'var(--color-success)',
    USB_ATTACH: 'var(--color-warning)',
    USB_ACCESS: 'var(--color-warning)',
    FILE_UPLOAD: 'var(--color-warning)',
    FILE_DROP: 'var(--color-warning)',
    DATA_ACCESS: 'var(--color-critical)',
    VIEW_DWELL: 'var(--color-text-faint)',
    HEARTBEAT: 'var(--color-text-faint)',
  }

  return (
    <Panel
      title="Live telemetry stream"
      subtitle="Real user moments captured in real time"
      actions={<Database className="size-3.5 text-[var(--color-text-faint)]" />}
      padded={false}
    >
      {error && <p className="px-4 py-3 text-[11px] text-[var(--color-critical)]">{error}</p>}
      {events.length === 0 ? (
        <p className="px-4 py-8 text-center text-[12px] text-[var(--color-text-faint)]">No telemetry captured yet — it appears as users work.</p>
      ) : (
        <ul className="divide-y divide-[var(--color-border)]">
          {events.map((e) => (
            <li key={e.id} className="flex items-center gap-3 px-3.5 py-2">
              <span className="num w-28 shrink-0 text-[9.5px] font-semibold" style={{ color: typeTone[e.event_type] ?? 'var(--color-text-faint)' }}>{e.event_type}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] text-[var(--color-text-muted)]">
                  {e.resource || e.device || e.location || [e.latitude, e.longitude].filter(Boolean).join(', ') || '—'}
                </p>
                <p className="text-[9.5px] text-[var(--color-text-faint)]">{e.source} · {e.ip_address ?? 'no ip'} · {new Date(e.occurred_at).toLocaleTimeString()}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

const inputCls = "h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-3 text-[12px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none focus:border-[var(--color-border-strong)]"

export function Settings() {
  const { user } = useAuth()
  const myRole = user?.role ?? 'VIEWER'
  const canManage = myRole === 'ADMIN'
  const canViewStaff = STAFF_VIEW_ROLES.includes(myRole)

  const [threshold, setThreshold] = useState(65)
  const [offHoursWeight, setOffHoursWeight] = useState(72)
  const [peerWeight, setPeerWeight] = useState(58)
  const [minConfidence, setMinConfidence] = useState(70)
  const [dedupeWindow, setDedupeWindow] = useState(15)
  const [retention, setRetention] = useState<'90d' | '1y' | '3y' | '7y'>('1y')

  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(detectors.map((d) => [d.name, d.status !== 'training'])),
  )

  const [channels, setChannels] = useState({
    siem: true,
    slack: true,
    email: false,
    pagerduty: true,
    webhook: false,
  })

  const [policy, setPolicy] = useState({
    pseudonymise: true,
    justifiedAccess: true,
    autoContain: false,
    legalHold: true,
  })

  const [watchlist, setWatchlist] = useState(
    employees.filter((e) => e.status === 'watchlist').map((e) => e.id),
  )

  const watched = employees.filter((e) => watchlist.includes(e.id))

  return (
    <div className="space-y-4">
      {/* Page heading */}
      <div className="mb-2">
        <h1 className="text-[20px] font-bold text-[var(--color-text)]">Detection Policies</h1>
        <p className="mt-1 text-[13px] text-[var(--color-text-muted)]">
          Configure how Sentinel identifies and prioritizes suspicious behaviour.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="space-y-4 xl:col-span-7">
          {canViewStaff ? (
            <UserManagementPanel canManage={canManage} />
          ) : (
            <Panel title="Employee directory" subtitle="Restricted">
              <p className="py-6 text-center text-[12px] text-[var(--color-text-faint)]">
                Your role ({ROLE_LABELS[myRole] ?? myRole}) does not include staff directory access. Contact your administrator.
              </p>
            </Panel>
          )}
          <RecentTelemetryPanel />
        </div>
        <div className="space-y-4 xl:col-span-5">
          {canManage && <AgentKeysPanel />}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Detection sensitivity"
          subtitle="Tune the ensemble's decision boundary. Changes take effect on the next scoring cycle."
          actions={<span className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-faint)]"><Sliders className="size-3" /> live</span>}
        >
          <div className="divide-y divide-[var(--color-border)]">
            <Slider label="Global alert threshold" value={threshold} onChange={setThreshold} unit="/100" hint="Composite risk above this value raises an alert." />
            <Slider label="Off-hours weight" value={offHoursWeight} onChange={setOffHoursWeight} unit="%" hint="How strongly activity inside 22:00–06:00 contributes to the anomaly score." />
            <Slider label="Peer deviation weight" value={peerWeight} onChange={setPeerWeight} unit="%" hint="Weight applied to distance from the peer-group centroid." />
            <Slider label="Minimum model confidence" value={minConfidence} onChange={setMinConfidence} unit="%" hint="Detections below this confidence are logged but kept out of the triage queue." />
            <Slider label="Alert de-duplication window" value={dedupeWindow} onChange={setDedupeWindow} min={5} max={120} step={5} unit=" min" hint="Repeat detections inside this window collapse into one case." />
          </div>
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Active detectors" subtitle="Disabling a detector removes it from the ensemble immediately">
            <div className="divide-y divide-[var(--color-border)]">
              {detectors.map((d) => (
                <Toggle
                  key={d.name}
                  label={d.name}
                  description={`${d.family} · F1 ${d.f1.toFixed(3)} · drift ${d.drift.toFixed(2)}`}
                  checked={enabled[d.name] ?? false}
                  onChange={(v) => setEnabled((s) => ({ ...s, [d.name]: v }))}
                  accent={d.status === 'degraded' ? '#D97706' : 'var(--color-primary)'}
                />
              ))}
            </div>
          </Panel>

          <Panel title="Alert routing" subtitle="Where confirmed detections are delivered" actions={<Bell className="size-3.5 text-[var(--color-text-faint)]" />}>
            <div className="divide-y divide-[var(--color-border)]">
              <Toggle label="SIEM forwarder" description="Push normalised events to the enterprise SIEM." checked={channels.siem} onChange={(v) => setChannels((s) => ({ ...s, siem: v }))} />
              <Toggle label="SOC Slack channel" description="#soc-insider-threat, critical and high only." checked={channels.slack} onChange={(v) => setChannels((s) => ({ ...s, slack: v }))} />
              <Toggle label="Email digest" description="Hourly rollup to the threat-hunting distribution list." checked={channels.email} onChange={(v) => setChannels((s) => ({ ...s, email: v }))} />
              <Toggle label="PagerDuty on-call" description="Page the on-call analyst for critical severity." checked={channels.pagerduty} onChange={(v) => setChannels((s) => ({ ...s, pagerduty: v }))} />
              <Toggle label="Outbound webhook" description="POST the full case payload to a custom endpoint." checked={channels.webhook} onChange={(v) => setChannels((s) => ({ ...s, webhook: v }))} />
            </div>
          </Panel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Watchlist"
          subtitle={`${watched.length} identities under enhanced monitoring`}
          padded={false}
        >
          {watched.length === 0 ? (
            <p className="px-4 py-12 text-center text-[12px] text-[var(--color-text-faint)]">No identities on the watchlist.</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {watched.map((e) => {
                const tone = riskTone(e.riskScore)
                return (
                  <li key={e.id} className="flex items-center gap-3 px-3.5 py-2.5 transition-colors duration-150 hover:bg-[var(--color-hover)]">
                    <Avatar initials={e.initials} department={e.department} size={32} ring={tone.hex} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-[var(--color-text)]">{e.name}</p>
                      <p className="truncate text-[10px] text-[var(--color-text-faint)]">
                        {e.title} · <span className="num">{e.peerGroup}</span> · <span className="num">{e.drift.toFixed(1)}σ</span>
                      </p>
                    </div>
                    <span className="num shrink-0 text-[13px] font-semibold" style={{ color: tone.hex }}>{e.riskScore}</span>
                    <button
                      type="button"
                      onClick={() => setWatchlist((w) => w.filter((id) => id !== e.id))}
                      title={`Remove ${e.name} from watchlist`}
                      className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] text-[var(--color-text-faint)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          <div className="flex items-center gap-2 border-t border-[var(--color-border)] px-3.5 py-3">
            <button
              type="button"
              onClick={() => setWatchlist(employees.filter((e) => e.status === 'watchlist').map((e) => e.id))}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-1.5 text-[10.5px] font-medium text-[var(--color-text-muted)] transition-colors duration-150 hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
            >
              Restore suggested watchlist
            </button>
            <span className="text-[10px] text-[var(--color-text-faint)]">Suggested by drift &gt; 3.0σ in the last 24 h</span>
          </div>
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          <Panel title="Data governance" subtitle="How monitored activity is stored" actions={<Database className="size-3.5 text-[var(--color-text-faint)]" />}>
            <div className="mb-1 flex items-center justify-between gap-3">
              <span className="text-[11.5px] font-medium text-[var(--color-text)]">Event retention</span>
              <Segmented size="sm" value={retention} onChange={setRetention} options={[{ value: '90d', label: '90D' }, { value: '1y', label: '1Y' }, { value: '3y', label: '3Y' }, { value: '7y', label: '7Y' }]} />
            </div>
            <p className="mb-3 text-[10px] text-[var(--color-text-faint)]">
              Raw access events are retained for {retention === '90d' ? '90 days' : retention === '1y' ? '1 year' : retention === '3y' ? '3 years' : '7 years'} before aggregation.
            </p>
            <div className="divide-y divide-[var(--color-border)] border-t border-[var(--color-border)]">
              <Toggle label="Pseudonymise identity fields" description="Store stable hashes instead of directory names." checked={policy.pseudonymise} onChange={(v) => setPolicy((s) => ({ ...s, pseudonymise: v }))} />
              <Toggle label="Require justification to view" description="Analysts must record a reason before rendering content." checked={policy.justifiedAccess} onChange={(v) => setPolicy((s) => ({ ...s, justifiedAccess: v }))} />
              <Toggle label="Automatic session containment" description="Auto-revoke sessions at critical severity." checked={policy.autoContain} onChange={(v) => setPolicy((s) => ({ ...s, autoContain: v }))} />
              <Toggle label="Legal hold exemption" description="Never act on identities under legal hold." checked={policy.legalHold} onChange={(v) => setPolicy((s) => ({ ...s, legalHold: v }))} />
            </div>
          </Panel>

          <Panel title="Audit" subtitle="Every analyst action is recorded">
            <ul className="space-y-2.5">
              {[
                { who: 'A. Reyes', what: 'Contained session for U-2291', when: '09:44 UTC', icon: ShieldCheck },
                { who: 'A. Reyes', what: 'Opened case ALT-4821', when: '09:41 UTC', icon: ShieldCheck },
                { who: 'system', what: 'Peer baselines retrained', when: '06:00 UTC', icon: Fingerprint },
                { who: 'M. Okafor', what: 'Dismissed ALT-4789 as benign', when: '05:58 UTC', icon: ShieldCheck },
                { who: 'system', what: 'Threshold raised 60 → 65', when: 'Yesterday', icon: Sliders },
              ].map((row, i) => {
                const Icon = row.icon
                return (
                  <li key={i} className="flex items-center gap-3">
                    <span className="grid size-7 shrink-0 place-items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-faint)]">
                      <Icon className="size-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[11px] text-[var(--color-text-muted)]">{row.what}</p>
                      <p className="text-[9.5px] text-[var(--color-text-faint)]">{row.who}</p>
                    </div>
                    <span className="num shrink-0 text-[10px] text-[var(--color-text-faint)]">{row.when}</span>
                  </li>
                )
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  )
}
