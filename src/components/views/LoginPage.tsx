import { useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, ShieldAlert } from 'lucide-react'
import { useAuth } from '../../lib/auth'
import { Logomark } from '../layout/Logomark'

export function LoginPage() {
  const { login, loading, error, clearError } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
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
          <h1 className="mb-1 text-center text-[18px] font-semibold text-[var(--color-text)]">
            Sign in
          </h1>
          <p className="mb-8 text-center text-[12.5px] text-[var(--color-text-muted)]">
            Access the Command Center
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 rounded-lg border border-[var(--color-critical-border)] bg-[var(--color-critical-bg)] px-3.5 py-2.5 text-[12px] text-[var(--color-critical)]">
                <ShieldAlert className="size-4 shrink-0" />
                <span>{error}</span>
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
                onChange={(e) => { setEmail(e.target.value); clearError() }}
                placeholder="you@sentinel.demo"
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
                  onChange={(e) => { setPassword(e.target.value); clearError() }}
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
        </div>

        {/* Demo credentials hint */}
        <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-4 py-3">
          <p className="mb-2 text-[10px] font-semibold tracking-[0.12em] text-[var(--color-text-faint)] uppercase">
            Demo Credentials
          </p>
          <div className="space-y-1 text-[11px] text-[var(--color-text-muted)]">
            <p>
              <span className="font-medium text-[var(--color-text-secondary)]">Admin:</span>{' '}
              admin@sentinel.demo / Admin123!
            </p>
            <p>
              <span className="font-medium text-[var(--color-text-secondary)]">Analyst:</span>{' '}
              sarah.chen@sentinel.demo / Analyst123!
            </p>
            <p>
              <span className="font-medium text-[var(--color-text-secondary)]">Viewer:</span>{' '}
              viewer@sentinel.demo / Viewer123!
            </p>
          </div>
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
