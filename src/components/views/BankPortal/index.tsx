import { useCallback, useEffect, useState } from 'react'
import {
  ArrowLeft, Banknote, Bell, Building2, CheckCircle2,
  ChevronRight, ClipboardList, CreditCard, FileText, FolderOpen,
  HelpCircle, Home, Landmark, LifeBuoy, Loader2, Mail, MapPin, Phone, Plus,
  Search, Send, Shield, User, X,
} from 'lucide-react'
import { cn } from '../../../lib/utils'
import { formatInr, initialsOf, relTime } from './bankUtils'
import {
  getBankProfile, getBranches, searchCustomers, getCustomerDetail, getAccountTransactions,
  searchTransactions, createTransfer, getLoans, updateLoan, getKycCases, updateKycCase,
  getStatement, getDocuments, createDocument, createLoan, getPortalNotifications,
  markPortalNotificationRead, markAllPortalNotificationsRead, getTickets, createTicket,
  type BankProfile, type BranchInfo, type BankCustomer, type BankAccount,
  type BankTransaction, type BankLoan, type BankKycCase, type BankDocument,
  type PortalNotification, type BankTicket, type StatementData, type Paged,
} from '../../../lib/bankApi'

type PortalView =
  | 'home' | 'customers' | 'customer' | 'transactions' | 'transfer' | 'loans'
  | 'kyc' | 'documents' | 'branch' | 'notifications' | 'support'

const NAV: Array<{ id: PortalView; label: string; icon: typeof Home }> = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'customers', label: 'Customers', icon: User },
  { id: 'transactions', label: 'Transactions', icon: ArrowLeft },
  { id: 'transfer', label: 'Fund Transfer', icon: Send },
  { id: 'loans', label: 'Loans', icon: Landmark },
  { id: 'kyc', label: 'KYC', icon: Shield },
  { id: 'documents', label: 'Documents', icon: FolderOpen },
  { id: 'branch', label: 'My Branch', icon: Building2 },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'support', label: 'Support', icon: LifeBuoy },
]

const ROLE_LABEL: Record<string, string> = {
  TELLER: 'Teller',
  RELATIONSHIP_MANAGER: 'Relationship Manager',
  BRANCH_MANAGER: 'Branch Manager',
  COMPLIANCE_OFFICER: 'Compliance Officer',
  OPERATIONS_MANAGER: 'Operations Manager',
}

/* Small primitives ---------------------------------------------------- */

function StatCard({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <div className="card animate-fade-up p-4">
      <p className="text-[10px] font-semibold tracking-[0.08em] text-[var(--color-text-faint)] uppercase">{label}</p>
      <p className="num mt-1.5 text-[22px] font-bold" style={{ color: tone ?? 'var(--color-text)' }}>{value}</p>
      {sub && <p className="mt-0.5 text-[10.5px] text-[var(--color-text-faint)]">{sub}</p>}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    SUCCESS: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    ACTIVE: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    VERIFIED: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    APPROVED: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    DISBURSED: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    RESOLVED: 'text-[var(--color-success)] bg-[var(--color-success-bg)] ring-[var(--color-success-border)]',
    CLOSED: 'text-[var(--color-text-faint)] bg-[var(--color-surface)] ring-[var(--color-border)]',
    ARCHIVED: 'text-[var(--color-text-faint)] bg-[var(--color-surface)] ring-[var(--color-border)]',
    PENDING: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    UNDER_REVIEW: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    IN_REVIEW: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    IN_PROGRESS: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    UPLOADED: 'text-[var(--color-info)] bg-[var(--color-info-bg)] ring-[var(--color-info-border)]',
    SUBMITTED: 'text-[var(--color-info)] bg-[var(--color-info-bg)] ring-[var(--color-info-border)]',
    OPEN: 'text-[var(--color-info)] bg-[var(--color-info-bg)] ring-[var(--color-info-border)]',
    EXPIRED: 'text-[var(--color-warning)] bg-[var(--color-warning-bg)] ring-[var(--color-warning-border)]',
    FAILED: 'text-[var(--color-critical)] bg-[var(--color-critical-bg)] ring-[var(--color-critical-border)]',
    REJECTED: 'text-[var(--color-critical)] bg-[var(--color-critical-bg)] ring-[var(--color-critical-border)]',
  }
  return (
    <span className={cn('inline-flex items-center rounded-md px-2 py-0.5 text-[10px] font-medium tracking-wide ring-1 ring-inset', map[status] ?? 'text-[var(--color-text-muted)] bg-[var(--color-surface)] ring-[var(--color-border)]')}>
      {status.replaceAll('_', ' ')}
    </span>
  )
}

function Avatar({ name, size = 32 }: { name: string; size?: number }) {
  return (
    <span
      className="grid shrink-0 place-items-center rounded-[9px] bg-gradient-to-br from-[hsl(210_30%_26%)] to-[hsl(210_30%_14%)] font-semibold text-[#f5f7fa] ring-1 ring-white/10"
      style={{ width: size, height: size, fontSize: size * 0.34 }}
    >
      {initialsOf(name)}
    </span>
  )
}

const inputCls = 'h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-[12.5px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]'

function Toolbar({ children }: { children: React.ReactNode }) {
  return <div className="mb-3 flex flex-wrap items-center gap-2">{children}</div>
}

function Empty({ text }: { text: string }) {
  return <p className="py-10 text-center text-[12px] text-[var(--color-text-faint)]">{text}</p>
}

function Spinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-[12px] text-[var(--color-text-faint)]">
      <Loader2 className="size-4 animate-spin" /> Loading…
    </div>
  )
}

/* ==================================================================== */
/* Portal app                                                           */
/* ==================================================================== */

export default function BankPortal() {
  const [profile, setProfile] = useState<BankProfile | null>(null)
  const [view, setView] = useState<PortalView>('home')
  const [selectedCustomerId, setSelectedCustomerId] = useState<string | null>(null)
  const [notifOpen, setNotifOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const { logout } = useAuthSafe()

  useEffect(() => {
    getBankProfile().then(setProfile).catch(() => {})
  }, [])

  const can = useCallback((perm: string) => profile?.permissions.includes(perm) ?? false, [profile])

  const navItems = NAV.filter((n) => {
    if (n.id === 'transfer') return can('transfers')
    if (n.id === 'loans') return can('loans')
    if (n.id === 'kyc') return can('kyc')
    if (n.id === 'documents') return can('documents')
    return true
  })

  if (!profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
        <div className="size-6 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text)]" />
      </div>
    )
  }

  const openCustomer = (id: string) => { setSelectedCustomerId(id); setView('customer') }

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* Sidebar */}
      <aside className={cn('flex h-full shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-card)] transition-all duration-200', sidebarCollapsed ? 'w-[60px]' : 'w-[228px]')}>
        <div className="flex h-[54px] shrink-0 items-center gap-2.5 border-b border-[var(--color-border)] px-4">
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-[var(--color-primary)] text-[var(--color-primary-text)]">
            <Landmark className="size-4" />
          </span>
          {!sidebarCollapsed && (
            <div className="min-w-0">
              <p className="truncate text-[13px] leading-tight font-bold">Apna Bank</p>
              <p className="text-[9px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase">Staff Portal</p>
            </div>
          )}
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {navItems.map((n) => {
            const Icon = n.icon
            const activeItem = view === n.id || (n.id === 'customers' && view === 'customer')
            return (
              <button
                key={n.id}
                type="button"
                onClick={() => setView(n.id)}
                title={sidebarCollapsed ? n.label : undefined}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                  activeItem
                    ? 'bg-[var(--color-surface)] font-medium text-[var(--color-text)]'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]',
                )}
              >
                <span className={cn('grid size-7 shrink-0 place-items-center rounded-md', activeItem ? 'bg-[var(--color-primary)] text-[var(--color-primary-text)]' : 'bg-[var(--color-surface)] text-[var(--color-text-muted)]')}>
                  <Icon className="size-3.5" />
                </span>
                {!sidebarCollapsed && <span className="truncate text-[12.5px]">{n.label}</span>}
              </button>
            )
          })}
        </nav>
        <div className="shrink-0 border-t border-[var(--color-border)] p-3">
          {!sidebarCollapsed && profile && (
            <div className="mb-2 flex items-center gap-2">
              <Avatar name={profile.name} size={30} />
              <div className="min-w-0">
                <p className="truncate text-[11.5px] font-medium">{profile.name}</p>
                <p className="text-[9.5px] text-[var(--color-text-faint)]">{ROLE_LABEL[profile.role] ?? profile.role}{profile.employee_code ? ` · ${profile.employee_code}` : ''}</p>
              </div>
            </div>
          )}
          <button type="button" onClick={() => setSidebarCollapsed(!sidebarCollapsed)} className="mb-1 w-full rounded-md px-2 py-1 text-left text-[10.5px] text-[var(--color-text-faint)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]">
            {sidebarCollapsed ? '»' : '« Collapse'}
          </button>
          <button type="button" onClick={() => void logout()} className="w-full rounded-md px-2 py-1 text-left text-[10.5px] text-[var(--color-critical)] hover:bg-[var(--color-critical-bg)]">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-card)] px-4">
          <div className="flex min-w-0 items-center gap-1.5 text-[12px] text-[var(--color-text-muted)]">
            <span>Portal</span>
            <ChevronRight className="size-3 text-[var(--color-text-faint)]" />
            <span className="font-medium text-[var(--color-text)]">{NAV.find((n) => n.id === view)?.label ?? 'Customer'}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-full border border-[var(--color-border)] px-2.5 py-1 text-[10.5px] text-[var(--color-text-muted)] sm:flex">
              <Building2 className="size-3" /> {profile.branch_name ?? 'Unassigned branch'}
            </span>
            <div className="relative">
              <button type="button" onClick={() => setNotifOpen(!notifOpen)} className="relative grid size-8 place-items-center rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]" aria-label="Notifications">
                <Bell className="size-4" />
                <NotifDot />
              </button>
              {notifOpen && <NotifPanel onOpenAll={() => { setNotifOpen(false); setView('notifications') }} />}
            </div>
            <button type="button" onClick={() => setView('home')} className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-[var(--color-hover)]">
              <Avatar name={profile.name} size={28} />
              <span className="hidden text-left md:block">
                <span className="block text-[11.5px] leading-tight font-medium">{profile.name}</span>
                <span className="block text-[9.5px] text-[var(--color-text-faint)]">{ROLE_LABEL[profile.role] ?? profile.role}</span>
              </span>
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="min-h-0 flex-1 overflow-y-auto p-5">
          {view === 'home' && <PortalHome profile={profile} onNavigate={setView} />}
          {view === 'customers' && <CustomersView onOpenCustomer={openCustomer} />}
          {view === 'customer' && selectedCustomerId && (
            <CustomerDetail customerId={selectedCustomerId} onBack={() => setView('customers')} />
          )}
          {view === 'transactions' && <TransactionsView />}
          {view === 'transfer' && can('transfers') && <TransferView onDone={() => setView('home')} />}
          {view === 'loans' && can('loans') && <LoansView />}
          {view === 'kyc' && can('kyc') && <KycView />}
          {view === 'documents' && can('documents') && <DocumentsView />}
          {view === 'branch' && <BranchView branchCode={profile.branch_code} />}
          {view === 'notifications' && <NotificationsView />}
          {view === 'support' && <SupportView />}
        </main>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------- */
/* Notification bell (shared)                                           */
/* -------------------------------------------------------------------- */

import { useAuth } from '../../../lib/auth'

function useAuthSafe() {
  return useAuth()
}

let notifVersion = 0

function NotifDot() {
  const [unread, setUnread] = useState(0)
  useEffect(() => {
    let alive = true
    getPortalNotifications().then((r) => { if (alive) setUnread(r.unread) }).catch(() => {})
    return () => { alive = false }
  }, [notifVersion])
  return unread > 0 ? (
    <span className="absolute top-1 right-1 grid size-3.5 place-items-center rounded-full bg-[var(--color-critical)] text-[8px] font-bold text-white">
      {unread > 9 ? '9+' : unread}
    </span>
  ) : null
}

function NotifPanel({ onOpenAll }: { onOpenAll: () => void }) {
  const [items, setItems] = useState<PortalNotification[]>([])
  useEffect(() => {
    getPortalNotifications().then((r) => setItems(r.items.slice(0, 6))).catch(() => {})
  }, [notifVersion])
  return (
    <div className="overlay animate-menu-in absolute top-full right-0 z-50 mt-1.5 w-[320px] rounded-lg p-2">
      <p className="px-2 pb-2 text-[11px] font-semibold tracking-wide text-[var(--color-text-muted)] uppercase">Notifications</p>
      {items.length === 0 ? (
        <p className="px-2 py-4 text-center text-[11px] text-[var(--color-text-faint)]">You're all caught up.</p>
      ) : (
        <ul className="space-y-1">
          {items.map((n) => (
            <li key={n.id} className={cn('rounded-md p-2.5', n.read ? 'bg-transparent' : 'bg-[var(--color-surface)]')}>
              <p className="text-[11.5px] font-medium">{n.title}</p>
              {n.body && <p className="mt-0.5 line-clamp-2 text-[10.5px] text-[var(--color-text-muted)]">{n.body}</p>}
              <p className="mt-1 text-[9.5px] text-[var(--color-text-faint)]">{relTime(n.created_at)}</p>
            </li>
          ))}
        </ul>
      )}
      <button type="button" onClick={onOpenAll} className="mt-2 w-full rounded-md px-2 py-1.5 text-center text-[11px] text-[var(--color-primary)] hover:bg-[var(--color-hover)]">
        View all
      </button>
    </div>
  )
}

/* ==================================================================== */
/* Home                                                                 */
/* ==================================================================== */

function PortalHome({ profile, onNavigate }: {
  profile: BankProfile
  onNavigate: (v: PortalView) => void
}) {
  const [recent, setRecent] = useState<BankTransaction[]>([])
  const [notifs, setNotifs] = useState<PortalNotification[]>([])
  const [branch, setBranch] = useState<BranchInfo | null>(null)

  useEffect(() => {
    searchTransactions({ page_size: 8 }).then((r) => setRecent(r.items)).catch(() => {})
    getPortalNotifications().then((r) => setNotifs(r.items.filter((n) => !n.read).slice(0, 4))).catch(() => {})
    if (profile.branch_code) {
      getBranches().then((bs) => setBranch(bs.find((b) => b.code === profile.branch_code) ?? null)).catch(() => {})
    }
  }, [profile.branch_code])

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[20px] font-bold">Good day, {profile.name.split(' ')[0]}</h1>
        <p className="mt-0.5 text-[12.5px] text-[var(--color-text-muted)]">
          {ROLE_LABEL[profile.role] ?? profile.role} · {profile.branch_name} · {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Working capital assigned" value={formatInr(48_500_000)} sub="Branch cash ceiling" />
        <StatCard label="My customers" value="142" sub="Active relationships" />
        <StatCard label="Open tasks" value="7" sub="Loans + KYC reviews" tone="var(--color-warning)" />
        <StatCard label="Today's sign-in" value={profile.last_login ? new Date(profile.last_login).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'} sub={profile.mfa_enabled ? 'MFA verified' : 'MFA off'} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="card p-4 xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-[13px] font-semibold">Recent transactions across branch</h2>
            <button type="button" onClick={() => onNavigate('transactions')} className="text-[11px] text-[var(--color-primary)] hover:underline">View all</button>
          </div>
          <TxnTable txns={recent} compact />
        </div>

        <div className="space-y-4">
          <div className="card p-4">
            <h2 className="mb-2 text-[13px] font-semibold">Unread alerts</h2>
            {notifs.length === 0 ? (
              <p className="py-4 text-center text-[11px] text-[var(--color-text-faint)]">Nothing pending.</p>
            ) : (
              <ul className="space-y-2">
                {notifs.map((n) => (
                  <li key={n.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2.5">
                    <p className="text-[11.5px] font-medium">{n.title}</p>
                    {n.body && <p className="mt-0.5 line-clamp-2 text-[10.5px] text-[var(--color-text-muted)]">{n.body}</p>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="card p-4">
            <h2 className="mb-2 text-[13px] font-semibold">My branch</h2>
            {branch ? (
              <div className="space-y-1.5 text-[11.5px] text-[var(--color-text-muted)]">
                <p className="font-medium text-[var(--color-text)]">{branch.name}</p>
                <p className="num">IFSC {branch.ifsc}</p>
                <p className="flex items-start gap-1.5"><MapPin className="mt-0.5 size-3 shrink-0" />{branch.address}</p>
                <p className="flex items-center gap-1.5"><Phone className="size-3 shrink-0" />{branch.phone}</p>
                <button type="button" onClick={() => onNavigate('branch')} className="mt-1 text-[11px] text-[var(--color-primary)] hover:underline">Branch details</button>
              </div>
            ) : (
              <p className="text-[11px] text-[var(--color-text-faint)]">Branch info unavailable.</p>
            )}
          </div>

          <div className="card p-4">
            <h2 className="mb-2 text-[13px] font-semibold">Quick actions</h2>
            <div className="grid grid-cols-2 gap-2">
              {canTransfer(profile) && (
                <button type="button" onClick={() => onNavigate('transfer')} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-[11.5px] hover:border-[var(--color-border-strong)]">
                  <Send className="size-3.5" /> New transfer
                </button>
              )}
              {profile.permissions.includes('loans') && (
                <button type="button" onClick={() => onNavigate('loans')} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-[11.5px] hover:border-[var(--color-border-strong)]">
                  <Landmark className="size-3.5" /> Loan pipeline
                </button>
              )}
              {profile.permissions.includes('kyc') && (
                <button type="button" onClick={() => onNavigate('kyc')} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-[11.5px] hover:border-[var(--color-border-strong)]">
                  <Shield className="size-3.5" /> KYC queue
                </button>
              )}
              <button type="button" onClick={() => onNavigate('customers')} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-[11.5px] hover:border-[var(--color-border-strong)]">
                <Search className="size-3.5" /> Find customer
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function canTransfer(p: BankProfile) {
  return p.permissions.includes('transfers')
}

/* ==================================================================== */
/* Customers                                                            */
/* ==================================================================== */

function CustomersView({ onOpenCustomer }: { onOpenCustomer: (id: string) => void }) {
  const [q, setQ] = useState('')
  const [segment, setSegment] = useState('')
  const [data, setData] = useState<Paged<BankCustomer> | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    searchCustomers({ q: q || undefined, segment: segment || undefined, page, page_size: 10 })
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [q, segment, page])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-[20px] font-bold">Customer search</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Find customers by name, ID, phone or email. Access is logged.</p>
      </div>
      <div className="card p-4">
        <Toolbar>
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-[var(--color-text-faint)]" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} placeholder="Search customers…" className={cn(inputCls, 'pl-9')} />
          </div>
          <select value={segment} onChange={(e) => { setSegment(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All segments</option>
            {['RETAIL', 'PREMIUM', 'BUSINESS', 'STAFF'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Toolbar>

        {loading ? <Spinner /> : !data || data.items.length === 0 ? <Empty text="No customers match." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-[10px] tracking-wide text-[var(--color-text-faint)] uppercase">
                  <th className="pb-2 pr-3 font-medium">Customer</th>
                  <th className="pb-2 pr-3 font-medium">ID</th>
                  <th className="pb-2 pr-3 font-medium">Segment</th>
                  <th className="pb-2 pr-3 font-medium">KYC</th>
                  <th className="pb-2 pr-3 font-medium">Phone</th>
                  <th className="pb-2 pr-3 font-medium">Branch</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="border-b border-[var(--color-border)]/60 hover:bg-[var(--color-hover)]">
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <Avatar name={c.name} size={26} />
                        <div>
                          <p className="font-medium">{c.name}</p>
                          <p className="text-[10px] text-[var(--color-text-faint)]">{c.city}</p>
                        </div>
                      </div>
                    </td>
                    <td className="num py-2.5 pr-3 text-[var(--color-text-muted)]">{c.customer_id}</td>
                    <td className="py-2.5 pr-3"><StatusPill status={c.segment ?? ''} /></td>
                    <td className="py-2.5 pr-3"><StatusPill status={c.kyc_status ?? ''} /></td>
                    <td className="num py-2.5 pr-3 text-[var(--color-text-muted)]">{c.phone}</td>
                    <td className="num py-2.5 pr-3 text-[var(--color-text-muted)]">{c.home_branch_code}</td>
                    <td className="py-2.5 text-right">
                      <button type="button" onClick={() => onOpenCustomer(c.id)} className="rounded-md border border-[var(--color-border)] px-2 py-1 text-[10.5px] hover:border-[var(--color-border-strong)]">
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total_pages > 1 && (
          <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--color-text-muted)]">
            <span>{data.total} customers</span>
            <div className="flex items-center gap-1.5">
              <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Prev</button>
              <span className="num">{page} / {data.total_pages}</span>
              <button type="button" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ==================================================================== */
/* Customer 360                                                         */
/* ==================================================================== */

function CustomerDetail({ customerId, onBack }: { customerId: string; onBack: () => void }) {
  const [c, setC] = useState<BankCustomer | null>(null)
  const [activeAccount, setActiveAccount] = useState<BankAccount | null>(null)
  const [txns, setTxns] = useState<BankTransaction[]>([])
  const [showStatement, setShowStatement] = useState(false)
  const [statement, setStatement] = useState<StatementData | null>(null)

  useEffect(() => {
    getCustomerDetail(customerId).then((d) => {
      setC(d)
      if (d.accounts.length > 0) setActiveAccount(d.accounts[0])
    }).catch(() => {})
  }, [customerId])

  useEffect(() => {
    if (activeAccount) {
      getAccountTransactions({ accountId: activeAccount.id, page_size: 12 }).then((r) => setTxns(r.items)).catch(() => {})
    }
  }, [activeAccount])

  const loadStatement = (months: number) => {
    if (!activeAccount) return
    setStatement(null)
    setShowStatement(true)
    getStatement(activeAccount.id, months).then(setStatement).catch(() => {})
  }

  if (!c) return <Spinner />

  return (
    <div className="space-y-4">
      <button type="button" onClick={onBack} className="flex items-center gap-1.5 text-[12px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
        <ArrowLeft className="size-3.5" /> Back to search
      </button>

      {/* Header card */}
      <div className="card flex flex-wrap items-center gap-4 p-5">
        <Avatar name={c.name} size={52} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[18px] font-bold">{c.name}</h1>
            <StatusPill status={c.kyc_status ?? ''} />
            <StatusPill status={c.segment ?? ''} />
          </div>
          <p className="num mt-0.5 text-[11.5px] text-[var(--color-text-muted)]">{c.customer_id} · KYC valid till {c.kyc_expiry ? new Date(c.kyc_expiry).toLocaleDateString('en-IN') : '—'}</p>
        </div>
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-[11.5px] text-[var(--color-text-muted)] sm:grid-cols-3">
          <span className="flex items-center gap-1.5"><Mail className="size-3" />{c.email}</span>
          <span className="num flex items-center gap-1.5"><Phone className="size-3" />{c.phone}</span>
          <span className="flex items-center gap-1.5"><MapPin className="size-3" />{c.city}</span>
          <span className="num">PAN {c.pan_masked}</span>
          <span className="num">Aadhaar {c.aadhaar_masked}</span>
          <span>RM {c.relationship_manager}</span>
        </div>
      </div>

      {/* Accounts */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {c.accounts.map((a) => (
          <button key={a.id} type="button" onClick={() => setActiveAccount(a)} className={cn('card p-4 text-left transition-colors', activeAccount?.id === a.id && 'ring-1 ring-[var(--color-primary)]')}>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-[12px] font-medium"><CreditCard className="size-3.5 text-[var(--color-text-faint)]" />{a.account_type}</span>
              <StatusPill status={a.status} />
            </div>
            <p className="num mt-2 text-[15px] font-bold">{formatInr(a.balance, a.currency)}</p>
            <p className="num mt-0.5 text-[11px] text-[var(--color-text-faint)]">{a.account_number_masked}{a.scheme ? ` · ${a.scheme}` : ''}</p>
          </button>
        ))}
      </div>

      {/* Txns + statement */}
      {activeAccount && (
        <div className="card">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3">
            <div>
              <h2 className="text-[13px] font-semibold">Account {activeAccount.account_number_masked}</h2>
              <p className="text-[10.5px] text-[var(--color-text-faint)]">Recent activity</p>
            </div>
            <div className="flex items-center gap-1.5">
              <button type="button" onClick={() => loadStatement(3)} className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] hover:border-[var(--color-border-strong)]">3M statement</button>
              <button type="button" onClick={() => loadStatement(6)} className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] hover:border-[var(--color-border-strong)]">6M statement</button>
              <button type="button" onClick={() => loadStatement(12)} className="rounded-md border border-[var(--color-border)] px-2.5 py-1.5 text-[11px] hover:border-[var(--color-border-strong)]">12M statement</button>
            </div>
          </div>

          <TxnTable txns={txns} showBalance />

          {showStatement && (
            <div className="border-t border-[var(--color-border)] p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-[12.5px] font-semibold">Statement — last {statement?.period_months ?? '…'} months</h3>
                <button type="button" onClick={() => setShowStatement(false)} className="text-[var(--color-text-faint)] hover:text-[var(--color-text)]"><X className="size-4" /></button>
              </div>
              {!statement ? <Spinner /> : (
                <>
                  <div className="mb-3 grid grid-cols-3 gap-3 text-[12px]">
                    <div className="rounded-lg border border-[var(--color-border)] p-2.5">
                      <p className="text-[9.5px] text-[var(--color-text-faint)] uppercase">Total credits</p>
                      <p className="num mt-0.5 font-semibold text-[var(--color-success)]">{formatInr(statement.summary.total_credits)}</p>
                    </div>
                    <div className="rounded-lg border border-[var(--color-border)] p-2.5">
                      <p className="text-[9.5px] text-[var(--color-text-faint)] uppercase">Total debits</p>
                      <p className="num mt-0.5 font-semibold text-[var(--color-critical)]">{formatInr(statement.summary.total_debits)}</p>
                    </div>
                    <div className="rounded-lg border border-[var(--color-border)] p-2.5">
                      <p className="text-[9.5px] text-[var(--color-text-faint)] uppercase">Transactions</p>
                      <p className="num mt-0.5 font-semibold">{statement.summary.txn_count}</p>
                    </div>
                  </div>
                  <TxnTable txns={statement.transactions} showBalance compact />
                  <p className="mt-2 text-[10px] text-[var(--color-text-faint)]">Generated {new Date(statement.generated_at).toLocaleString('en-IN')} · download recorded for audit.</p>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ==================================================================== */
/* Transactions (global search)                                         */
/* ==================================================================== */

function TransactionsView() {
  const [q, setQ] = useState('')
  const [channel, setChannel] = useState('')
  const [status, setStatus] = useState('')
  const [data, setData] = useState<Paged<BankTransaction> | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    searchTransactions({ q: q || undefined, channel: channel || undefined, status: status || undefined, page, page_size: 15 })
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [q, channel, status, page])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-[20px] font-bold">Transactions</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Search by transaction ID, counterparty or narration.</p>
      </div>
      <div className="card p-4">
        <Toolbar>
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-[var(--color-text-faint)]" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} placeholder="TXN-… or counterparty" className={cn(inputCls, 'pl-9')} />
          </div>
          <select value={channel} onChange={(e) => { setChannel(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All channels</option>
            {['UPI', 'NEFT', 'IMPS', 'ATM', 'POS', 'BRANCH', 'ACH'].map((ch) => <option key={ch}>{ch}</option>)}
          </select>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All statuses</option>
            {['SUCCESS', 'PENDING', 'FAILED'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </Toolbar>
        {loading ? <Spinner /> : !data || data.items.length === 0 ? <Empty text="No transactions match." /> : (
          <>
            <TxnTable txns={data.items} showBalance />
            {data.total_pages > 1 && (
              <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--color-text-muted)]">
                <span>{data.total} transactions</span>
                <div className="flex items-center gap-1.5">
                  <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Prev</button>
                  <span className="num">{page} / {data.total_pages}</span>
                  <button type="button" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

/* Shared txn table ---------------------------------------------------- */

function TxnTable({ txns, showBalance = false, compact = false }: { txns: BankTransaction[]; showBalance?: boolean; compact?: boolean }) {
  if (txns.length === 0) return <Empty text="No transactions." />
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-left text-[10px] tracking-wide text-[var(--color-text-faint)] uppercase">
            <th className="px-4 py-2 font-medium">Txn ID</th>
            <th className="px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Details</th>
            <th className="px-4 py-2 font-medium">Channel</th>
            <th className="px-4 py-2 text-right font-medium">Amount</th>
            {showBalance && <th className="px-4 py-2 text-right font-medium">Balance</th>}
            <th className="px-4 py-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {txns.map((t) => (
            <tr key={t.id} className="border-b border-[var(--color-border)]/60 hover:bg-[var(--color-hover)]">
              <td className="num px-4 py-2.5 whitespace-nowrap text-[var(--color-text-muted)]">{compact ? t.txn_id.slice(-6) : t.txn_id}</td>
              <td className="px-4 py-2.5 whitespace-nowrap text-[var(--color-text-muted)]">{new Date(t.posted_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</td>
              <td className="max-w-[260px] px-4 py-2.5">
                <p className="truncate">{t.counterparty ?? t.narration}</p>
                <p className="truncate text-[10px] text-[var(--color-text-faint)]">{t.category}{t.counterparty_account_masked ? ` · ${t.counterparty_account_masked}` : ''}</p>
              </td>
              <td className="px-4 py-2.5"><span className="num rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-muted)]">{t.channel}</span></td>
              <td className={cn('num px-4 py-2.5 text-right font-semibold whitespace-nowrap', t.direction === 'CR' ? 'text-[var(--color-success)]' : 'text-[var(--color-text)]')}>
                {t.direction === 'CR' ? '+' : '−'}{formatInr(t.amount)}
              </td>
              {showBalance && <td className="num px-4 py-2.5 text-right whitespace-nowrap text-[var(--color-text-muted)]">{t.balance_after != null ? formatInr(t.balance_after) : '—'}</td>}
              <td className="px-4 py-2.5"><StatusPill status={t.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ==================================================================== */
/* Fund transfer                                                        */
/* ==================================================================== */

function TransferView({ onDone }: { onDone: () => void }) {
  const [customers, setCustomers] = useState<BankCustomer[]>([])
  const [fromId, setFromId] = useState('')
  const [toAcc, setToAcc] = useState('')
  const [amount, setAmount] = useState('')
  const [channel, setChannel] = useState('IMPS')
  const [narration, setNarration] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<TransferResultShape | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [accounts, setAccounts] = useState<BankAccount[]>([])

  useEffect(() => {
    searchCustomers({ page_size: 25 }).then((r) => setCustomers(r.items)).catch(() => {})
  }, [])

  const selectedCustomer = customers.find((c) => c.id === fromId)

  useEffect(() => {
    if (selectedCustomer && selectedCustomer.accounts.length > 0) {
      setAccounts(selectedCustomer.accounts)
      setFromIdAccount(selectedCustomer.accounts[0].id)
    } else {
      setAccounts([])
      setFromIdAccount('')
    }
  }, [fromId])

  const [fromAccId, setFromIdAccount] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)
    setSubmitting(true)
    try {
      const res = await createTransfer({
        from_account_id: fromAccId,
        to_account_number: toAcc,
        amount: Number(amount),
        channel,
        narration: narration || undefined,
      })
      setResult(res)
      setToAcc(''); setAmount(''); setNarration('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Transfer failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-[620px] space-y-4">
      <div>
        <h1 className="text-[20px] font-bold">Fund transfer</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Move funds between customer accounts. Portal limit ₹10,00,000 per transaction.</p>
      </div>

      {result ? (
        <div className="card p-6 text-center">
          <CheckCircle2 className="mx-auto size-10 text-[var(--color-success)]" />
          <h2 className="mt-2 text-[16px] font-bold">Transfer successful</h2>
          <p className="num mt-1 text-[13px] text-[var(--color-text-muted)]">{result.txn_id} · {result.channel}</p>
          <p className="num mt-3 text-[24px] font-bold">{formatInr(result.amount)}</p>
          <p className="num mt-1 text-[11.5px] text-[var(--color-text-muted)]">{result.from_account_masked} → {result.to_account_masked}</p>
          <p className="mt-1 text-[11px] text-[var(--color-text-faint)]">Ref {result.reference} · New balance {formatInr(result.balance_after)}</p>
          <div className="mt-4 flex justify-center gap-2">
            <button type="button" onClick={() => setResult(null)} className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-[12px] font-semibold text-[var(--color-primary-text)]">New transfer</button>
            <button type="button" onClick={onDone} className="rounded-lg border border-[var(--color-border)] px-4 py-2 text-[12px]">Back to home</button>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} className="card space-y-4 p-5">
          {error && <p className="rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11.5px] text-[var(--color-critical)]">{error}</p>}

          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Customer (debit)</span>
            <select value={fromId} onChange={(e) => setFromId(e.target.value)} required className={inputCls}>
              <option value="">Select customer…</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.customer_id}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Debit account</span>
            <select value={fromAccId} onChange={(e) => setFromIdAccount(e.target.value)} required disabled={!selectedCustomer} className={cn(inputCls, 'disabled:opacity-50')}>
              <option value="">Select account…</option>
              {accounts.map((a) => <option key={a.id} value={a.id}>{a.account_number_masked} · {a.account_type} · {formatInr(a.balance)}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Credit account number</span>
            <input value={toAcc} onChange={(e) => setToAcc(e.target.value)} placeholder="11–12 digit account number" required minLength={8} maxLength={20} className={cn(inputCls, 'num')} />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Amount (₹)</span>
              <input type="number" min={1} step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} required className={cn(inputCls, 'num')} />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Channel</span>
              <select value={channel} onChange={(e) => setChannel(e.target.value)} className={inputCls}>
                {['IMPS', 'NEFT', 'UPI'].map((ch) => <option key={ch}>{ch}</option>)}
              </select>
            </label>
          </div>

          <label className="block">
            <span className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">Narration (optional)</span>
            <input value={narration} onChange={(e) => setNarration(e.target.value)} placeholder="e.g. Rent settlement" className={inputCls} />
          </label>

          <button type="submit" disabled={submitting} className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] text-[13px] font-semibold text-[var(--color-primary-text)] transition-opacity hover:opacity-90 disabled:opacity-40">
            {submitting ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            {submitting ? 'Processing…' : 'Transfer now'}
          </button>
        </form>
      )}
    </div>
  )
}

type TransferResultShape = {
  txn_id: string; status: string; amount: number; from_account_masked: string
  to_account_masked: string; balance_after: number; channel: string; reference: string; posted_at: string
}

/* ==================================================================== */
/* Loans                                                                */
/* ==================================================================== */

function LoansView() {
  const [data, setData] = useState<Paged<BankLoan> | null>(null)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    getLoans({ status: status || undefined, page, page_size: 10 }).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [status, page])

  useEffect(() => { load() }, [load])

  const decide = async (loanId: string, newStatus: string) => {
    setBusyId(loanId)
    try {
      await updateLoan(loanId, { status: newStatus })
      await load()
    } catch { /* error surfaced on reload */ }
    finally { setBusyId(null) }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-bold">Loan applications</h1>
          <p className="text-[12px] text-[var(--color-text-muted)]">Pipeline of retail loan proposals.</p>
        </div>
        <button type="button" onClick={() => setShowNew(!showNew)} className="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-3 py-2 text-[12px] font-semibold text-[var(--color-primary-text)]">
          <Plus className="size-3.5" /> New application
        </button>
      </div>

      {showNew && <NewLoanForm onCreated={() => { setShowNew(false); load() }} />}

      <div className="card p-4">
        <Toolbar>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All statuses</option>
            {['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'DISBURSED'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </Toolbar>
        {loading ? <Spinner /> : !data || data.items.length === 0 ? <Empty text="No loan applications." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-[10px] tracking-wide text-[var(--color-text-faint)] uppercase">
                  <th className="py-2 pr-3 font-medium">Loan ID</th>
                  <th className="py-2 pr-3 font-medium">Customer</th>
                  <th className="py-2 pr-3 font-medium">Product</th>
                  <th className="py-2 pr-3 text-right font-medium">Amount</th>
                  <th className="py-2 pr-3 text-right font-medium">EMI</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Age</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((l) => (
                  <tr key={l.id} className="border-b border-[var(--color-border)]/60 hover:bg-[var(--color-hover)]">
                    <td className="num py-2.5 pr-3">{l.loan_id}</td>
                    <td className="py-2.5 pr-3">{l.customer_name}</td>
                    <td className="py-2.5 pr-3">{l.product}</td>
                    <td className="num py-2.5 pr-3 text-right">{formatInr(l.amount)}</td>
                    <td className="num py-2.5 pr-3 text-right text-[var(--color-text-muted)]">{l.emi ? formatInr(l.emi) : '—'}</td>
                    <td className="py-2.5 pr-3"><StatusPill status={l.status} /></td>
                    <td className="py-2.5 pr-3 text-[var(--color-text-faint)]">{relTime(l.created_at)}</td>
                    <td className="py-2.5">
                      {(l.status === 'SUBMITTED' || l.status === 'UNDER_REVIEW') ? (
                        <div className="flex gap-1.5">
                          <button type="button" disabled={busyId === l.id} onClick={() => decide(l.loan_id, 'APPROVED')} className="rounded-md border border-[var(--color-success-border)] px-2 py-1 text-[10.5px] text-[var(--color-success)] hover:bg-[var(--color-success-bg)] disabled:opacity-40">Approve</button>
                          <button type="button" disabled={busyId === l.id} onClick={() => decide(l.loan_id, 'REJECTED')} className="rounded-md border border-[var(--color-critical-border)] px-2 py-1 text-[10.5px] text-[var(--color-critical)] hover:bg-[var(--color-critical-bg)] disabled:opacity-40">Reject</button>
                        </div>
                      ) : <span className="text-[10.5px] text-[var(--color-text-faint)]">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total_pages > 1 && (
          <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Prev</button>
            <span className="num">{page} / {data.total_pages}</span>
            <button type="button" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </div>
    </div>
  )
}

function NewLoanForm({ onCreated }: { onCreated: () => void }) {
  const [customers, setCustomers] = useState<BankCustomer[]>([])
  const [form, setForm] = useState({ customer_id: '', product: 'HOME', amount: '', tenure_months: '60', purpose: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    searchCustomers({ page_size: 50 }).then((r) => setCustomers(r.items)).catch(() => {})
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await createLoan({
        customer_id: form.customer_id,
        product: form.product,
        amount: Number(form.amount),
        tenure_months: Number(form.tenure_months),
        purpose: form.purpose || undefined,
      })
      onCreated()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit application')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="card grid grid-cols-1 gap-3 p-4 sm:grid-cols-3">
      {error && <p className="rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11.5px] text-[var(--color-critical)] sm:col-span-3">{error}</p>}
      <label className="block sm:col-span-2">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Customer</span>
        <select required value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} className={inputCls}>
          <option value="">Select customer…</option>
          {customers.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.customer_id}</option>)}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Product</span>
        <select value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })} className={inputCls}>
          {['HOME', 'AUTO', 'PERSONAL', 'GOLD', 'EDUCATION'].map((p) => <option key={p}>{p}</option>)}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Amount (₹)</span>
        <input required type="number" min={10000} value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className={cn(inputCls, 'num')} />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Tenure (months)</span>
        <input required type="number" min={6} value={form.tenure_months} onChange={(e) => setForm({ ...form, tenure_months: e.target.value })} className={cn(inputCls, 'num')} />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Purpose</span>
        <input value={form.purpose} onChange={(e) => setForm({ ...form, purpose: e.target.value })} placeholder="Optional" className={inputCls} />
      </label>
      <div className="sm:col-span-3">
        <button type="submit" disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-[12px] font-semibold text-[var(--color-primary-text)] disabled:opacity-40">
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />} Submit application
        </button>
      </div>
    </form>
  )
}

/* ==================================================================== */
/* KYC                                                                  */
/* ==================================================================== */

function KycView() {
  const [data, setData] = useState<Paged<BankKycCase> | null>(null)
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    getKycCases({ status: status || undefined, page, page_size: 10 }).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [status, page])

  useEffect(() => { load() }, [load])

  const setCaseStatus = async (caseNumber: string, newStatus: string) => {
    setBusyId(caseNumber)
    try {
      await updateKycCase(caseNumber, { status: newStatus })
      await load()
    } catch { /* ignore */ }
    finally { setBusyId(null) }
  }

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-[20px] font-bold">KYC verification</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Review and verify customer KYC records.</p>
      </div>
      <div className="card p-4">
        <Toolbar>
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All statuses</option>
            {['PENDING', 'IN_REVIEW', 'VERIFIED', 'REJECTED'].map((s) => <option key={s}>{s}</option>)}
          </select>
        </Toolbar>
        {loading ? <Spinner /> : !data || data.items.length === 0 ? <Empty text="No KYC cases." /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-left text-[10px] tracking-wide text-[var(--color-text-faint)] uppercase">
                  <th className="py-2 pr-3 font-medium">Case</th>
                  <th className="py-2 pr-3 font-medium">Customer</th>
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Priority</th>
                  <th className="py-2 pr-3 font-medium">Pending docs</th>
                  <th className="py-2 pr-3 font-medium">Due</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((k) => (
                  <tr key={k.id} className="border-b border-[var(--color-border)]/60 hover:bg-[var(--color-hover)]">
                    <td className="num py-2.5 pr-3">{k.case_number}</td>
                    <td className="py-2.5 pr-3">{k.customer_name}</td>
                    <td className="py-2.5 pr-3">{k.case_type}</td>
                    <td className="py-2.5 pr-3"><StatusPill status={k.priority === 'HIGH' ? 'FAILED' : k.priority === 'MEDIUM' ? 'PENDING' : 'CLOSED'} /></td>
                    <td className="py-2.5 pr-3">
                      {k.documents_pending.length === 0 ? <span className="text-[var(--color-success)]">None</span> : (
                        <span className="flex flex-wrap gap-1">{k.documents_pending.map((d) => <span key={d} className="num rounded bg-[var(--color-surface)] px-1.5 py-0.5 text-[9.5px]">{d}</span>)}</span>
                      )}
                    </td>
                    <td className="py-2.5 pr-3 text-[var(--color-text-muted)]">{k.due_at ? new Date(k.due_at).toLocaleDateString('en-IN') : '—'}</td>
                    <td className="py-2.5 pr-3"><StatusPill status={k.status} /></td>
                    <td className="py-2.5">
                      {k.status !== 'VERIFIED' && k.status !== 'REJECTED' ? (
                        <div className="flex gap-1.5">
                          <button type="button" disabled={busyId === k.case_number} onClick={() => setCaseStatus(k.case_number, 'VERIFIED')} className="rounded-md border border-[var(--color-success-border)] px-2 py-1 text-[10.5px] text-[var(--color-success)] hover:bg-[var(--color-success-bg)] disabled:opacity-40">Verify</button>
                          <button type="button" disabled={busyId === k.case_number} onClick={() => setCaseStatus(k.case_number, 'REJECTED')} className="rounded-md border border-[var(--color-critical-border)] px-2 py-1 text-[10.5px] text-[var(--color-critical)] hover:bg-[var(--color-critical-bg)] disabled:opacity-40">Reject</button>
                        </div>
                      ) : <span className="text-[10.5px] text-[var(--color-text-faint)]">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.total_pages > 1 && (
          <div className="mt-3 flex items-center justify-end gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Prev</button>
            <span className="num">{page} / {data.total_pages}</span>
            <button type="button" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} className="rounded-md border border-[var(--color-border)] px-2 py-1 disabled:opacity-40">Next</button>
          </div>
        )}
      </div>
    </div>
  )
}

/* ==================================================================== */
/* Documents                                                            */
/* ==================================================================== */

function DocumentsView() {
  const [data, setData] = useState<Paged<BankDocument> | null>(null)
  const [q, setQ] = useState('')
  const [docType, setDocType] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    getDocuments({ q: q || undefined, doc_type: docType || undefined, page, page_size: 12 }).then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [q, docType, page])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-bold">Documents</h1>
          <p className="text-[12px] text-[var(--color-text-muted)]">Customer document vault for your branch.</p>
        </div>
        <button type="button" onClick={() => setShowUpload(!showUpload)} className="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-3 py-2 text-[12px] font-semibold text-[var(--color-primary-text)]">
          <Plus className="size-3.5" /> Register upload
        </button>
      </div>

      {showUpload && <UploadDocForm onDone={() => { setShowUpload(false); load() }} />}

      <div className="card p-4">
        <Toolbar>
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-3.5 -translate-y-1/2 text-[var(--color-text-faint)]" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1) }} placeholder="Search documents…" className={cn(inputCls, 'pl-9')} />
          </div>
          <select value={docType} onChange={(e) => { setDocType(e.target.value); setPage(1) }} className={cn(inputCls, 'w-auto')}>
            <option value="">All types</option>
            {['ID_PROOF', 'ADDRESS_PROOF', 'INCOME_PROOF', 'FORM_16', 'STATEMENT', 'OTHER'].map((t) => <option key={t}>{t}</option>)}
          </select>
        </Toolbar>
        {loading ? <Spinner /> : !data || data.items.length === 0 ? <Empty text="No documents." /> : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((d) => (
              <div key={d.id} className="rounded-lg border border-[var(--color-border)] p-3 transition-colors hover:border-[var(--color-border-strong)]">
                <div className="flex items-start gap-2.5">
                  <span className="grid size-8 shrink-0 place-items-center rounded-md bg-[var(--color-surface)] text-[var(--color-text-muted)]"><FileText className="size-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] font-medium">{d.title}</p>
                    <p className="num truncate text-[10px] text-[var(--color-text-faint)]">{d.doc_id} · {d.customer_name ?? 'General'}</p>
                    <p className="mt-0.5 text-[10px] text-[var(--color-text-faint)]">{d.file_name} · {d.file_size ? `${(d.file_size / 1024).toFixed(0)} KB` : '—'}</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <StatusPill status={d.status} />
                  <span className="text-[9.5px] text-[var(--color-text-faint)]">v{d.version} · {relTime(d.created_at)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function UploadDocForm({ onDone }: { onDone: () => void }) {
  const [customers, setCustomers] = useState<BankCustomer[]>([])
  const [form, setForm] = useState({ customer_id: '', title: '', doc_type: 'ID_PROOF', file_name: '', file_size: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    searchCustomers({ page_size: 50 }).then((r) => setCustomers(r.items)).catch(() => {})
  }, [])

  const onFile = (f: File | null) => {
    if (!f) return
    setForm((s) => ({ ...s, file_name: f.name, file_size: String(f.size) }))
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await createDocument({
        customer_id: form.customer_id || undefined,
        title: form.title,
        doc_type: form.doc_type,
        file_name: form.file_name || `${form.title.replace(/\s+/g, '_').toLowerCase()}.pdf`,
        file_size: form.file_size ? Number(form.file_size) : undefined,
        mime: 'application/pdf',
      })
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="card grid grid-cols-1 gap-3 p-4 sm:grid-cols-2">
      {error && <p className="rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11.5px] text-[var(--color-critical)] sm:col-span-2">{error}</p>}
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Customer (optional)</span>
        <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })} className={inputCls}>
          <option value="">General / branch document</option>
          {customers.map((c) => <option key={c.id} value={c.id}>{c.name} — {c.customer_id}</option>)}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Document type</span>
        <select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })} className={inputCls}>
          {['ID_PROOF', 'ADDRESS_PROOF', 'INCOME_PROOF', 'FORM_16', 'STATEMENT', 'OTHER'].map((t) => <option key={t}>{t}</option>)}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Title</span>
        <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. PAN copy — Ravi Kumar" className={inputCls} />
      </label>
      <label className="block">
        <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Attach file (metadata only)</span>
        <input type="file" onChange={(e) => onFile(e.target.files?.[0] ?? null)} className="h-9 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 text-[11px] text-[var(--color-text-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface)] file:px-2 file:py-1 file:text-[10px]" />
      </label>
      <div className="sm:col-span-2">
        <button type="submit" disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-[var(--color-primary)] px-4 py-2 text-[12px] font-semibold text-[var(--color-primary-text)] disabled:opacity-40">
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <FolderOpen className="size-3.5" />} Register document
        </button>
        <span className="ml-2 text-[10px] text-[var(--color-text-faint)]">File transfer is tracked by the document registry.</span>
      </div>
    </form>
  )
}

/* ==================================================================== */
/* Branch                                                               */
/* ==================================================================== */

function BranchView({ branchCode }: { branchCode?: string | null }) {
  const [branches, setBranches] = useState<BranchInfo[]>([])
  const [selected, setSelected] = useState(branchCode ?? '')

  useEffect(() => {
    getBranches().then(setBranches).catch(() => {})
  }, [])

  const b = branches.find((x) => x.code === selected) ?? branches[0]

  return (
    <div className="mx-auto max-w-[760px] space-y-4">
      <div>
        <h1 className="text-[20px] font-bold">Branch information</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Contact and operational details for your branches.</p>
      </div>
      <div className="card">
        <div className="flex flex-wrap gap-1.5 border-b border-[var(--color-border)] p-3">
          {branches.map((x) => (
            <button key={x.code} type="button" onClick={() => setSelected(x.code)} className={cn('rounded-md px-2.5 py-1.5 text-[11.5px]', b?.code === x.code ? 'bg-[var(--color-primary)] font-medium text-[var(--color-primary-text)]' : 'border border-[var(--color-border)] hover:bg-[var(--color-hover)]')}>
              {x.name}
            </button>
          ))}
        </div>
        {!b ? <Spinner /> : (
          <div className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[16px] font-bold">{b.name}</h2>
                <p className="num mt-0.5 text-[12px] text-[var(--color-text-muted)]">IFSC {b.ifsc} · Code {b.code}</p>
              </div>
              <span className="grid size-12 place-items-center rounded-xl bg-[var(--color-surface)]"><Building2 className="size-6 text-[var(--color-text-muted)]" /></span>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 text-[12.5px] sm:grid-cols-2">
              <div className="space-y-2 text-[var(--color-text-muted)]">
                <p className="flex items-start gap-2"><MapPin className="mt-0.5 size-3.5 shrink-0" />{b.address}, {b.city}, {b.state}</p>
                <p className="flex items-center gap-2"><Phone className="size-3.5 shrink-0" /><span className="num">{b.phone}</span></p>
              </div>
              <div className="space-y-2 text-[var(--color-text-muted)]">
                <p className="flex items-center gap-2"><User className="size-3.5 shrink-0" />Manager: <span className="font-medium text-[var(--color-text)]">{b.manager_name}</span></p>
                <p className="flex items-center gap-2"><Banknote className="size-3.5 shrink-0" />Counter hours: 09:30 – 15:30 IST</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ==================================================================== */
/* Notifications page                                                   */
/* ==================================================================== */

function NotificationsView() {
  const [items, setItems] = useState<PortalNotification[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    getPortalNotifications().then((r) => setItems(r.items)).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const markAll = async () => {
    await markAllPortalNotificationsRead().catch(() => {})
    notifVersion += 1
    load()
  }

  const markOne = async (id: string) => {
    await markPortalNotificationRead(id).catch(() => {})
    notifVersion += 1
    load()
  }

  return (
    <div className="mx-auto max-w-[680px] space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[20px] font-bold">Notifications</h1>
          <p className="text-[12px] text-[var(--color-text-muted)]">Bank announcements and your activity updates.</p>
        </div>
        <button type="button" onClick={() => void markAll()} className="rounded-lg border border-[var(--color-border)] px-3 py-2 text-[11.5px] hover:border-[var(--color-border-strong)]">Mark all read</button>
      </div>
      <div className="card divide-y divide-[var(--color-border)] p-0">
        {loading ? <Spinner /> : items.length === 0 ? <Empty text="No notifications." /> : items.map((n) => (
          <div key={n.id} className={cn('flex items-start gap-3 p-4', !n.read && 'bg-[var(--color-surface)]')}>
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-[var(--color-surface)] text-[var(--color-text-muted)]">
              {n.category === 'TRANSFERS' ? <Send className="size-3.5" /> : n.category === 'LOANS' ? <Landmark className="size-3.5" /> : n.category === 'KYC' ? <Shield className="size-3.5" /> : <Bell className="size-3.5" />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[12.5px] font-medium">{n.title}</p>
              {n.body && <p className="mt-0.5 text-[11.5px] text-[var(--color-text-muted)]">{n.body}</p>}
              <p className="mt-1 text-[9.5px] text-[var(--color-text-faint)]">{n.category} · {relTime(n.created_at)}</p>
            </div>
            {!n.read && (
              <button type="button" onClick={() => void markOne(n.id)} className="shrink-0 rounded-md border border-[var(--color-border)] px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:border-[var(--color-border-strong)]">
                Mark read
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ==================================================================== */
/* Support                                                              */
/* ==================================================================== */

function SupportView() {
  const [tickets, setTickets] = useState<Paged<BankTicket> | null>(null)
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ category: 'IT', subject: '', description: '', priority: 'MEDIUM' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    setLoading(true)
    getTickets({ page_size: 20 }).then(setTickets).catch(() => {}).finally(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await createTicket({ category: form.category, subject: form.subject, description: form.description || undefined, priority: form.priority })
      setForm({ category: 'IT', subject: '', description: '', priority: 'MEDIUM' })
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to raise ticket')
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[20px] font-bold">Support</h1>
        <p className="text-[12px] text-[var(--color-text-muted)]">Raise internal tickets for IT, operations or compliance help.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <form onSubmit={submit} className="card space-y-3 p-4 xl:col-span-2">
          {error && <p className="rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3 py-2 text-[11.5px] text-[var(--color-critical)]">{error}</p>}
          <div className="grid grid-cols-2 gap-2">
            <label className="block">
              <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Category</span>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className={inputCls}>
                {['IT', 'OPERATIONS', 'COMPLIANCE', 'HR', 'OTHER'].map((c) => <option key={c}>{c}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Priority</span>
              <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className={inputCls}>
                {['LOW', 'MEDIUM', 'HIGH'].map((p) => <option key={p}>{p}</option>)}
              </select>
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Subject</span>
            <input required value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Short summary" className={inputCls} />
          </label>
          <label className="block">
            <span className="mb-1 block text-[10.5px] text-[var(--color-text-secondary)]">Description</span>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={4} placeholder="What do you need help with?" className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-[12.5px] outline-none focus:border-[var(--color-border-strong)]" />
          </label>
          <button type="submit" disabled={busy} className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--color-primary)] text-[12px] font-semibold text-[var(--color-primary-text)] disabled:opacity-40">
            {busy ? <Loader2 className="size-3.5 animate-spin" /> : <HelpCircle className="size-3.5" />} Raise ticket
          </button>
          <p className="text-[10px] text-[var(--color-text-faint)]">IT helpdesk: ext. 4120 · Risk team: ext. 4185</p>
        </form>

        <div className="card p-0 xl:col-span-3">
          <div className="border-b border-[var(--color-border)] px-4 py-3">
            <h2 className="text-[13px] font-semibold">My tickets</h2>
          </div>
          {loading ? <Spinner /> : !tickets || tickets.items.length === 0 ? <Empty text="No tickets yet." /> : (
            <ul className="divide-y divide-[var(--color-border)]">
              {tickets.items.map((t) => (
                <li key={t.id} className="flex items-start gap-3 p-4">
                  <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-[var(--color-surface)] text-[var(--color-text-muted)]"><ClipboardList className="size-3.5" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12.5px] font-medium">{t.subject}</p>
                    <p className="num mt-0.5 text-[10px] text-[var(--color-text-faint)]">{t.ticket_number} · {t.category} · {t.assignee_name ?? 'Unassigned'}</p>
                    {t.resolution && <p className="mt-1 rounded bg-[var(--color-success-bg)] px-2 py-1 text-[10.5px] text-[var(--color-success)]">{t.resolution}</p>}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <StatusPill status={t.status} />
                    <span className="text-[9.5px] text-[var(--color-text-faint)]">{relTime(t.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
