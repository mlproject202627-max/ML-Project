import { useState, useRef, useEffect } from 'react'
import {
  Bell,
  ChevronDown,
  LogOut,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  Sun,
  Monitor,
  User,
} from 'lucide-react'
import { useAuth } from '../../lib/auth'
import { useTheme } from '../../lib/theme'
import { cn } from '../../lib/utils'

export function TopBar({
  breadcrumbs,
  searchQuery,
  onSearchChange,
  searchRef,
  sidebarCollapsed,
  onToggleSidebar,
}: {
  breadcrumbs: React.ReactNode
  searchQuery: string
  onSearchChange: (q: string) => void
  searchRef?: React.RefObject<HTMLInputElement | null>
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
}) {
  const { user, logout } = useAuth()
  const { theme, setTheme } = useTheme()
  const [showNotifications, setShowNotifications] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [showThemeMenu, setShowThemeMenu] = useState(false)

  const profileRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)
  const themeRef = useRef<HTMLDivElement>(null)

  // Close menus on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setShowProfile(false)
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifications(false)
      if (themeRef.current && !themeRef.current.contains(e.target as Node)) setShowThemeMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const initials = user?.name
    ?.split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase() || 'U'

  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : Monitor

  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-card)] px-4">
      {/* Sidebar toggle */}
      <button
        type="button"
        onClick={onToggleSidebar}
        className="grid size-7 shrink-0 place-items-center rounded-md text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
        aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {sidebarCollapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
      </button>

      {/* Breadcrumbs */}
      <div className="min-w-0 flex-1">{breadcrumbs}</div>

      {/* Search */}
      <div className="relative hidden min-w-0 md:block md:w-[240px] xl:w-[300px]">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-[var(--color-text-faint)]" />
        <input
          ref={searchRef}
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search…"
          className="h-8 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pr-8 pl-8 text-[12px] text-[var(--color-text)] transition-colors placeholder:text-[var(--color-text-faint)] focus:border-[var(--color-border-strong)] focus:outline-none"
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute top-1/2 right-2 -translate-y-1/2 text-[10px] text-[var(--color-text-faint)] hover:text-[var(--color-text)]"
          >
            clear
          </button>
        ) : (
          <kbd className="num pointer-events-none absolute top-1/2 right-2 hidden -translate-y-1/2 rounded border border-[var(--color-border)] bg-[var(--color-card)] px-1.5 py-0.5 text-[10px] text-[var(--color-text-faint)] xl:inline">
            ⌘K
          </kbd>
        )}
      </div>

      {/* Right cluster */}
      <div className="flex shrink-0 items-center gap-1.5">
        {/* Theme toggle */}
        <div ref={themeRef} className="relative">
          <button
            type="button"
            onClick={() => setShowThemeMenu(!showThemeMenu)}
            className="grid size-7 place-items-center rounded-md text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            aria-label="Toggle theme"
          >
            <ThemeIcon className="size-3.5" />
          </button>
          {showThemeMenu && (
            <div className="overlay animate-menu-in absolute top-full right-0 z-50 mt-1.5 w-[140px] rounded-lg p-1">
              {[
                { value: 'light' as const, label: 'Light', icon: Sun },
                { value: 'dark' as const, label: 'Dark', icon: Moon },
                { value: 'system' as const, label: 'System', icon: Monitor },
              ].map((opt) => {
                const Icon = opt.icon
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => { setTheme(opt.value); setShowThemeMenu(false) }}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[12px] transition-colors',
                      theme === opt.value
                        ? 'bg-[var(--color-surface)] font-medium text-[var(--color-text)]'
                        : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]'
                    )}
                  >
                    <Icon className="size-3.5" />
                    {opt.label}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Notifications */}
        <div ref={notifRef} className="relative">
          <button
            type="button"
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative grid size-7 place-items-center rounded-md text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
            aria-label="Notifications"
          >
            <Bell className="size-3.5" />
            <span className="absolute -top-0.5 -right-0.5 size-2 rounded-full bg-[var(--color-critical)]" />
          </button>
          {showNotifications && (
            <div className="overlay animate-menu-in absolute top-full right-0 z-50 mt-1.5 w-[280px] rounded-lg p-2">
              <p className="px-2 pb-2 text-[11px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wide">
                Notifications
              </p>
              <div className="space-y-1">
                <div className="rounded-md bg-[var(--color-critical-bg)] p-2.5">
                  <p className="text-[11px] font-medium text-[var(--color-critical)]">Critical anomaly detected</p>
                  <p className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">Omar Haddad — Lateral Movement</p>
                </div>
                <div className="rounded-md bg-[var(--color-warning-bg)] p-2.5">
                  <p className="text-[11px] font-medium text-[var(--color-warning)]">Investigation assigned</p>
                  <p className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">INV-4821 assigned to you</p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="mx-1 hidden h-5 w-px bg-[var(--color-border)] xl:block" />

        {/* Profile menu */}
        <div ref={profileRef} className="relative hidden xl:block">
          <button
            type="button"
            onClick={() => setShowProfile(!showProfile)}
            className="flex items-center gap-2 rounded-lg px-2 py-1 transition-colors hover:bg-[var(--color-hover)]"
          >
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-[var(--color-surface)] text-[11px] font-semibold text-[var(--color-text)] ring-1 ring-[var(--color-border)]">
              {initials}
            </span>
            <div className="min-w-0 text-left">
              <p className="truncate text-[11.5px] leading-tight font-medium text-[var(--color-text)]">
                {user?.name || 'User'}
              </p>
              <p className="text-[10px] text-[var(--color-text-faint)]">{user?.role || 'Role'}</p>
            </div>
            <ChevronDown className="size-3 text-[var(--color-text-faint)]" />
          </button>

          {showProfile && (
            <div className="overlay animate-menu-in absolute top-full right-0 z-50 mt-1.5 w-[180px] rounded-lg p-1">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[12px] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
              >
                <User className="size-3.5" /> Profile
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[12px] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover)] hover:text-[var(--color-text)]"
              >
                <Settings className="size-3.5" /> Settings
              </button>
              <div className="my-1 h-px bg-[var(--color-border)]" />
              <button
                type="button"
                onClick={() => logout()}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-[12px] text-[var(--color-critical)] transition-colors hover:bg-[var(--color-critical-bg)]"
              >
                <LogOut className="size-3.5" /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
