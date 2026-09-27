import { useEffect, useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, ShieldAlert, ShieldCheck, UserPlus } from 'lucide-react'
import { useAuth } from '../../lib/auth'
import { hasUsers, bootstrapAdmin } from '../../lib/api'
import { trackLogin } from '../../lib/telemetry'
import { Logomark } from '../layout/Logomark'

type Mode = 'checking' | 'login' | 'bootstrap'

export function LoginPage() {
  const { login, loading, error, clearError } = useAuth()
  const [mode, setMode] = useState<Mode>('checking')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  // Decide which screen to show: first-run bootstrap or normal login.
  useEffect(() => {
    let cancelled = false
    hasUsers()
      .then((r) => { if (!cancelled) setMode(r.hasUsers ? 'login' : 'bootstrap') })
      .catch(() => { if (!cancelled) setMode('login') }) // backend down → normal login UX
    return () => { cancelled = true }
  }, [])

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setSubmitting(true)
    try {
      await login(email, password)
    } catch {
      // error is set by useAuth
    } finally {
      setSubmitting(false)
    }
  }

  const handleBootstrap = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    if (!name || !email || !password) return
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters.')
      return
    }
    setSubmitting(true)
    try {
      await bootstrapAdmin({ name, email, password })
      trackLogin()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create the admin account.'
      setLocalError(message)
    } finally {
      setSubmitting(false)
    }
  }

  const isBootstrap = mode === 'bootstrap'
  const shownError = localError ?? error

  if (mode === 'checking') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
        <div className="size-6 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-text)]" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)] px-6">
      <div className="relative z-10 w-full max-w-[380px]">
        {/* Brand */}
        <div className="mb-10 flex flex-col items-center gap-3">
          <Logomark size={36} />
          <div className="text-center">
            <span className="block text-[15px] font-bold tracking-[0.16em] text-[var(--color-text)]">
              SENTINEL
            </span>
            <span className="mt-1 block text-[9.5px] tracking-[0.12em] text-[var(--color-text-faint)] uppercase">
              Insider Threat Detection
            </span>
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
          {isBootstrap ? (
            <>
              <div className="mb-6 flex items-center gap-2 rounded-lg border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-3 py-2 text-[11px] text-[var(--color-info)]">
                <ShieldCheck className="size-4 shrink-0" />
                <span>First run — create the administrator account. Further users are invited by admins.</span>
              </div>
              <h1 className="mb-1 text-center text-[18px] font-semibold text-[var(--color-text)]">
                Set up administrator
              </h1>
              <p className="mb-8 text-center text-[12.5px] text-[var(--color-text-muted)]">
                This account will manage users and detection policies
              </p>

              <form onSubmit={handleBootstrap} className="space-y-4">
                {shownError && (
                  <div className="flex items-center gap-2 rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3.5 py-2.5 text-[12px] text-[var(--color-critical)]">
                    <ShieldAlert className="size-4 shrink-0" />
                    <span>{shownError}</span>
                  </div>
                )}

                <div>
                  <label className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">
                    Full name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => { setName(e.target.value); setLocalError(null) }}
                    placeholder="Ada Lovelace"
                    autoComplete="name"
                    required
                    className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">
                    Work email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setLocalError(null) }}
                    placeholder="you@company.com"
                    autoComplete="email"
                    required
                    className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); setLocalError(null) }}
                      placeholder="Minimum 8 characters"
                      autoComplete="new-password"
                      minLength={8}
                      required
                      className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pr-10 pl-3.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-[var(--color-text-faint)] transition-colors hover:text-[var(--color-text-muted)]"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={submitting || loading || !name || !email || !password}
                  className="group flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] text-[13px] font-semibold text-[var(--color-primary-text)] transition-all duration-150 hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {submitting ? (
                    <span className="size-4 animate-spin rounded-full border-2 border-[var(--color-primary-text)]/20 border-t-[var(--color-primary-text)]" />
                  ) : (
                    <>
                      Create admin account
                      <UserPlus className="size-3.5 transition-transform duration-150 group-hover:translate-y-[-1px]" />
                    </>
                  )}
                </button>
              </form>
            </>
          ) : (
            <>
              <h1 className="mb-1 text-center text-[18px] font-semibold text-[var(--color-text)]">
                Sign in
              </h1>
              <p className="mb-8 text-center text-[12.5px] text-[var(--color-text-muted)]">
                Access the Command Center
              </p>

              <form onSubmit={handleLogin} className="space-y-4">
                {/* Error */}
                {shownError && (
                  <div className="flex items-center gap-2 rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3.5 py-2.5 text-[12px] text-[var(--color-critical)]">
                    <ShieldAlert className="size-4 shrink-0" />
                    <span>{shownError}</span>
                  </div>
                )}

                {/* Email */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); clearError(); setLocalError(null) }}
                    placeholder="you@company.com"
                    autoComplete="email"
                    required
                    className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]"
                  />
                </div>

                {/* Password */}
                <div>
                  <label className="mb-1.5 block text-[11px] font-medium text-[var(--color-text-secondary)]">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => { setPassword(e.target.value); clearError(); setLocalError(null) }}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      required
                      className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pr-10 pl-3.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none transition-colors focus:border-[var(--color-border-strong)]"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-[var(--color-text-faint)] transition-colors hover:text-[var(--color-text-muted)]"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>

                {/* Submit */}
                <button
                  type="submit"
                  disabled={submitting || loading || !email || !password}
                  className="group flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-primary)] text-[13px] font-semibold text-[var(--color-primary-text)] transition-all duration-150 hover:bg-[var(--color-primary-hover)] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {submitting ? (
                    <span className="size-4 animate-spin rounded-full border-2 border-[var(--color-primary-text)]/20 border-t-[var(--color-primary-text)]" />
                  ) : (
                    <>
                      Sign in
                      <ArrowRight className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5" />
                    </>
                  )}
                </button>
              </form>

              <p className="mt-6 text-center text-[10.5px] leading-relaxed text-[var(--color-text-faint)]">
                Accounts are created by your administrator.
                <br />
                Sign-in time, location and device are recorded for security monitoring.
              </p>
            </>
          )}
        </div>

        {/* Back to landing */}
        <p className="mt-6 text-center text-[11px] text-[var(--color-text-faint)]">
          <a href="/" className="text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]">
            ← Back to Sentinel
          </a>
        </p>
      </div>
    </div>
  )
}
