import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import { Sidebar } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import { Breadcrumbs } from './components/ui/Breadcrumbs'
import { DashboardSkeleton } from './components/ui/LoadingState'
import { AlertDrawer } from './components/detail/AlertDrawer'
import { EmployeeDrawer } from './components/detail/EmployeeDrawer'
import { navItem, type ViewId } from './lib/nav'
import { useAuth } from './lib/auth'

/* Landing page and login are eagerly loaded. */
import { LandingPage } from './components/views/LandingPage'
import { LoginPage } from './components/views/LoginPage'

/* Views are code-split. */
const Overview = lazy(() =>
  import('./components/views/Overview').then((m) => ({ default: m.Overview })),
)
const Behaviour = lazy(() =>
  import('./components/views/Behaviour').then((m) => ({ default: m.Behaviour })),
)
const Alerts = lazy(() =>
  import('./components/views/Alerts').then((m) => ({ default: m.Alerts })),
)
const Timeline = lazy(() =>
  import('./components/views/Timeline').then((m) => ({ default: m.Timeline })),
)
const Models = lazy(() =>
  import('./components/views/Models').then((m) => ({ default: m.Models })),
)
const Settings = lazy(() =>
  import('./components/views/Settings').then((m) => ({ default: m.Settings })),
)

export default function App() {
  const { user, loading } = useAuth()
  const [showLanding, setShowLanding] = useState(true)
  const [view, setView] = useState<ViewId>('overview')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const [alertId, setAlertId] = useState<string | null>(null)
  const [employeeId, setEmployeeId] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement | null>(null)

  const enterDashboard = useCallback(() => {
    setShowLanding(false)
  }, [])

  const openAlert = useCallback((id: string) => {
    setShowLanding(false)
    setEmployeeId(null)
    setAlertId(id)
  }, [])

  const openEmployee = useCallback((id: string) => {
    setShowLanding(false)
    setAlertId(null)
    setEmployeeId(id)
  }, [])

  const navigate = useCallback((id: ViewId) => {
    setShowLanding(false)
    setView(id)
    setSearchQuery('')
  }, [])

  // ⌘K / Ctrl+K
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  /* ── Landing page ── */
  if (showLanding) {
    return <LandingPage onEnterDashboard={enterDashboard} />
  }

  /* ── Login page (not authenticated) ── */
  if (!user) {
    if (loading) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
          <div className="size-6 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text)]" />
        </div>
      )
    }
    return <LoginPage />
  }

  /* ── Main App Shell ── */
  const item = navItem(view)

  return (
    <div className="relative z-[1] flex h-screen overflow-hidden bg-[var(--color-bg)] animate-fade-in">
      {/* Sidebar */}
      <Sidebar
        active={view}
        onNavigate={navigate}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <TopBar
          breadcrumbs={<Breadcrumbs items={item.breadcrumb} />}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          searchRef={searchRef}
          sidebarCollapsed={sidebarCollapsed}
          onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
        />

        {/* Page content */}
        <main className="scrollbar-none min-h-0 flex-1 overflow-y-auto p-5">
          <Suspense fallback={<DashboardSkeleton />}>
            {view === 'overview' && (
              <Overview
                live={true}
                range={'24h'}
                onSelectAlert={openAlert}
                onSelectEmployee={openEmployee}
                onOpenQueue={() => navigate('alerts')}
              />
            )}
            {view === 'behaviour' && (
              <Behaviour
                query={searchQuery}
                onSelectEmployee={openEmployee}
                selectedEmployeeId={employeeId}
              />
            )}
            {view === 'alerts' && (
              <Alerts query={searchQuery} onSelectAlert={openAlert} selectedAlertId={alertId} />
            )}
            {view === 'timeline' && (
              <Timeline
                live={true}
                onSelectAlert={openAlert}
                onSelectEmployee={openEmployee}
              />
            )}
            {view === 'models' && <Models />}
            {view === 'settings' && <Settings />}
          </Suspense>

          <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--color-border)] pt-4 text-[10px] text-[var(--color-text-faint)]">
            <span>
              Sentinel UEBA · demo build · all identities, events and detections are synthetic
              sample data
            </span>
            <span className="num">scoring pipeline · 6 detectors</span>
          </footer>
        </main>
      </div>

      {/* Drawers */}
      <AlertDrawer
        alertId={alertId}
        onClose={() => setAlertId(null)}
        onOpenEmployee={openEmployee}
      />
      <EmployeeDrawer
        employeeId={employeeId}
        onClose={() => setEmployeeId(null)}
        onOpenAlert={openAlert}
      />
    </div>
  )
}
