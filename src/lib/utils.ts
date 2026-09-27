import type { Department, Severity } from '../data/types'

export function cn(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}

export function formatNumber(n: number): string {
  return n.toLocaleString('en-US')
}

export function formatCompact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

/* ── Risk ramp ─────────────────────────────────────────────────── */
export interface Tone {
  label: string
  hex: string
  text: string
  bg: string
  ring: string
}

/**
 * Spec §11 risk bands, in one place.
 *
 * These boundaries are the contract between the backend and every screen that
 * colours a score: 0–20 LOW, 21–40 MODERATE, 41–60 ELEVATED, 61–80 HIGH,
 * 81–100 CRITICAL. They previously read 85/70/50 here, which meant a score the
 * API called ELEVATED rendered as "Low" — the same number described two
 * different ways depending on which side of the wire you read it from.
 *
 * Prefer the `level` the API returns when you have it; this is for raw scores.
 */
export function riskLevel(score: number): 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'CRITICAL' {
  if (score >= 81) return 'CRITICAL'
  if (score >= 61) return 'HIGH'
  if (score >= 41) return 'ELEVATED'
  if (score >= 21) return 'MODERATE'
  return 'LOW'
}

const TONE_BY_LEVEL: Record<ReturnType<typeof riskLevel>, Tone> = {
  CRITICAL: { label: 'Critical', hex: '#DC2626', text: 'text-[var(--color-critical)]', bg: 'bg-[var(--color-critical-bg)]', ring: 'ring-[var(--color-critical-border)]' },
  HIGH: { label: 'High', hex: '#D97706', text: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning-bg)]', ring: 'ring-[var(--color-warning-border)]' },
  // ELEVATED and MODERATE share a visual tone — the palette has four colours
  // and the spec has five bands — so the label is what distinguishes them.
  ELEVATED: { label: 'Elevated', hex: '#2563EB', text: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info-bg)]', ring: 'ring-[var(--color-info-border)]' },
  MODERATE: { label: 'Moderate', hex: '#2563EB', text: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info-bg)]', ring: 'ring-[var(--color-info-border)]' },
  LOW: { label: 'Low', hex: '#737373', text: 'text-[var(--color-text-muted)]', bg: 'bg-[var(--color-surface)]', ring: 'ring-[var(--color-border)]' },
}

export function riskTone(score: number): Tone {
  return TONE_BY_LEVEL[riskLevel(score)]
}

export const SEVERITY_HEX: Record<Severity, string> = {
  critical: '#DC2626',
  high: '#D97706',
  medium: '#2563EB',
  low: '#737373',
}

/* ── Graph palette ─────────────────────────────────────────────── */
export const GRAPH = {
  primary: '#22d3ee',
  secondary: '#a78bfa',
  tertiary: '#fba55a',
  alert: '#fb5a76',
  good: '#34d399',
  low: '#5ad0fb',
  grid: '#E5E5E5',
  axis: '#D4D4D4',
  tick: '#737373',
  neutral: '#A3A3A3',
  areaFrom: 'rgba(34, 211, 238, 0.25)',
  areaTo: 'rgba(34, 211, 238, 0)',
} as const

/* ── Department shade ──────────────────────────────────────────── */
const DEPT_SHADE: Record<Department, number> = {
  Engineering: 40,
  Finance: 25,
  'IT Ops': 50,
  Sales: 20,
  HR: 45,
  Legal: 30,
  Product: 55,
  Support: 15,
  Executive: 60,
  Contract: 22,
}

export function deptShade(department: Department): number {
  return DEPT_SHADE[department]
}

/* ── Time helpers ──────────────────────────────────────────────── */

/**
 * "12 min ago" against the *current* clock.
 *
 * This previously measured against `NOW`, a frozen constant exported by the
 * mock dataset. That was harmless while every timestamp in the UI also came
 * from the mock, and silently wrong the moment real events arrived: an access
 * recorded three minutes ago would be dated against a fixed point in the past
 * and render as weeks-old, or — for anything after that point — clamp to
 * "just now" forever. Live telemetry needs a live clock.
 */
export function relativeTime(iso: string): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'unknown'
  const mins = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} h ${mins % 60} min ago`
  return `${Math.floor(hrs / 24)} d ago`
}

export function clockTime(iso: string): string {
  return new Date(iso).toISOString().slice(11, 16)
}

export function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
  })
}

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
