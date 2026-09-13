import { NOW } from '../data/mock'
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

export function riskTone(score: number): Tone {
  if (score >= 85)
    return { label: 'Critical', hex: '#DC2626', text: 'text-[var(--color-critical)]', bg: 'bg-[var(--color-critical-bg)]', ring: 'ring-[var(--color-critical-border)]' }
  if (score >= 70)
    return { label: 'High', hex: '#D97706', text: 'text-[var(--color-warning)]', bg: 'bg-[var(--color-warning-bg)]', ring: 'ring-[var(--color-warning-border)]' }
  if (score >= 50)
    return { label: 'Medium', hex: '#2563EB', text: 'text-[var(--color-info)]', bg: 'bg-[var(--color-info-bg)]', ring: 'ring-[var(--color-info-border)]' }
  return { label: 'Low', hex: '#737373', text: 'text-[var(--color-text-muted)]', bg: 'bg-[var(--color-surface)]', ring: 'ring-[var(--color-border)]' }
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
export function relativeTime(iso: string): string {
  const then = new Date(iso)
  const mins = Math.max(0, Math.round((NOW.getTime() - then.getTime()) / 60000))
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
