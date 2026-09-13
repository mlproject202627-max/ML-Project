import {
  ArrowRight,
  Brain,
  ChevronRight,
  Eye,
  Search,
  ShieldAlert,
  ShieldCheck,
  Users,
} from 'lucide-react'

import { Logomark } from '../layout/Logomark'

const CAPABILITIES = [
  {
    icon: Users,
    title: 'Behaviour Analytics',
    description: 'Detect deviations from normal user behaviour patterns across the organization.',
  },
  {
    icon: ShieldAlert,
    title: 'Anomaly Detection',
    description: 'Identify suspicious activity patterns using ML-powered behavioural analysis.',
  },
  {
    icon: Brain,
    title: 'Risk Scoring',
    description: 'Prioritize users and events based on contextual behavioural risk assessment.',
  },
  {
    icon: Search,
    title: 'Investigation',
    description: 'Trace suspicious activity from initial detection through to resolution.',
  },
  {
    icon: ShieldCheck,
    title: 'ML Intelligence',
    description: 'Understand how machine-learning models contribute to insider-threat detection.',
  },
  {
    icon: Eye,
    title: 'Identity Monitoring',
    description: 'Continuously monitor privileged and high-risk identities for unusual behaviour.',
  },
]

const STEPS = [
  { number: '01', title: 'Collect', description: 'Observe user activity, access patterns, and behavioural signals.' },
  { number: '02', title: 'Analyse', description: 'ML models and rules detect deviations from established baselines.' },
  { number: '03', title: 'Detect', description: 'Risk scoring identifies the most critical threats for investigation.' },
  { number: '04', title: 'Investigate', description: 'Security analysts review, investigate, and resolve incidents.' },
]

const SIGNALS = [
  { value: '12,480', label: 'Identities Monitored' },
  { value: '113', label: 'Anomalies Detected' },
  { value: '42.8', label: 'Mean Risk Index' },
  { value: '6', label: 'Active Detectors' },
]

interface LandingPageProps {
  onEnterDashboard: () => void
}

export function LandingPage({ onEnterDashboard }: LandingPageProps) {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* ── Navbar ── */}
      <nav className="fixed top-0 right-0 left-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-card)]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Logomark size={26} />
            <span className="text-[13px] font-bold tracking-[0.14em] text-[var(--color-text)]">
              SENTINEL
            </span>
            <span className="hidden text-[9px] tracking-[0.1em] text-[var(--color-text-faint)] uppercase sm:block">
              Insider Threat UEBA
            </span>
          </div>

          <button
            type="button"
            onClick={onEnterDashboard}
            className="rounded-lg bg-[var(--color-primary)] px-4 py-2 text-[12px] font-medium text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)]"
          >
            Open Command Center
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden pt-16">
        <div className="relative z-10 mx-auto max-w-4xl px-6 text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-card)] px-4 py-1.5">
            <span className="size-1.5 rounded-full bg-[var(--color-success)]" />
            <span className="text-[10px] font-semibold tracking-[0.18em] text-[var(--color-text-muted)] uppercase">
              Insider Threat Detection · UEBA
            </span>
          </div>

          <h1 className="mb-6 text-[clamp(2.2rem,5.5vw,4rem)] leading-[1.08] font-bold tracking-tight text-[var(--color-text)]">
            Detect insider threats
            <br />
            before they become incidents.
          </h1>

          <p className="mx-auto mb-10 max-w-2xl text-[16px] leading-relaxed text-[var(--color-text-secondary)]">
            Behaviour-based security analytics that helps security teams identify unusual activity,
            understand risk, and investigate incidents — powered by machine learning.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={onEnterDashboard}
              className="group inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-6 py-3 text-[13px] font-semibold text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)]"
            >
              Enter Command Center
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </button>
            <button
              type="button"
              onClick={onEnterDashboard}
              className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] px-6 py-3 text-[13px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]"
            >
              Explore Detection Engine
            </button>
          </div>
        </div>
      </section>

      {/* ── Signal Strip ── */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-card)]">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-px md:grid-cols-4">
          {SIGNALS.map((signal) => (
            <div key={signal.label} className="flex flex-col items-center gap-1 px-6 py-8">
              <span className="num text-[28px] font-semibold tracking-tight text-[var(--color-text)]">
                {signal.value}
              </span>
              <span className="text-[11px] text-[var(--color-text-faint)]">{signal.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-[10px] font-semibold tracking-[0.2em] text-[var(--color-text-faint)] uppercase">
              How It Works
            </p>
            <h2 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
              From activity to intelligence
            </h2>
          </div>

          <div className="relative grid grid-cols-1 gap-8 md:grid-cols-4">
            <div className="pointer-events-none absolute top-12 left-[12.5%] right-[12.5%] hidden h-px bg-[var(--color-border)] md:block" />
            {STEPS.map((step) => (
              <div key={step.number} className="relative text-center">
                <div className="mx-auto mb-5 flex size-20 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-card)]">
                  <span className="num text-[22px] font-bold text-[var(--color-text)]">{step.number}</span>
                </div>
                <h3 className="mb-1.5 text-[15px] font-semibold text-[var(--color-text)]">{step.title}</h3>
                <p className="text-[12.5px] leading-relaxed text-[var(--color-text-muted)]">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Capabilities ── */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-card)] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="mb-14 text-center">
            <p className="mb-3 text-[10px] font-semibold tracking-[0.2em] text-[var(--color-text-faint)] uppercase">
              Capabilities
            </p>
            <h2 className="text-[28px] font-bold tracking-tight text-[var(--color-text)]">
              Enterprise-grade insider threat detection
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {CAPABILITIES.map((cap) => {
              const Icon = cap.icon
              return (
                <div
                  key={cap.title}
                  className="card card-hover rounded-xl p-6 transition-all duration-200"
                >
                  <div className="mb-4 grid size-10 place-items-center rounded-lg bg-[var(--color-surface)]">
                    <Icon className="size-5 text-[var(--color-text-muted)]" />
                  </div>
                  <h3 className="mb-1.5 text-[14px] font-semibold text-[var(--color-text)]">{cap.title}</h3>
                  <p className="text-[12.5px] leading-relaxed text-[var(--color-text-muted)]">{cap.description}</p>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ── Final CTA ── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="mb-6 text-[28px] font-bold tracking-tight text-[var(--color-text)]">
            Turn behavioural signals into security intelligence.
          </h2>
          <button
            type="button"
            onClick={onEnterDashboard}
            className="group inline-flex items-center gap-2 rounded-lg bg-[var(--color-primary)] px-6 py-3 text-[13px] font-semibold text-[var(--color-primary-text)] transition-colors hover:bg-[var(--color-primary-hover)]"
          >
            Enter Command Center
            <ChevronRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="border-t border-[var(--color-border)] px-6 py-12">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 md:flex-row md:justify-between">
          <div className="flex items-center gap-2.5">
            <Logomark size={22} />
            <span className="text-[13px] font-bold tracking-[0.12em] text-[var(--color-text)]">SENTINEL</span>
          </div>
          <p className="text-[11px] text-[var(--color-text-faint)]">
            © 2026 Sentinel · Insider Threat Detection Platform
          </p>
        </div>
      </footer>
    </div>
  )
}
