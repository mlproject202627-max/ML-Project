import {
  Activity,
  BrainCircuit,
  LayoutDashboard,
  Settings,
  ShieldAlert,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

/* ── View IDs ─────────────────────────────────────────────────── */
export type ViewId =
  | 'overview'
  | 'behaviour'
  | 'alerts'
  | 'timeline'
  | 'models'
  | 'settings'

/* ── Navigation Groups ─────────────────────────────────────────── */
export interface NavGroup {
  id: string
  label: string
  icon: LucideIcon
  items: NavItem[]
}

export interface NavItem {
  id: ViewId
  label: string
  icon: LucideIcon
  blurb: string
  breadcrumb: string[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    icon: LayoutDashboard,
    items: [
      {
        id: 'overview',
        label: 'Command Center',
        icon: LayoutDashboard,
        blurb: 'Monitor organizational risk, detected anomalies, and active investigations.',
        breadcrumb: ['Home', 'Command Center'],
      },
    ],
  },
  {
    id: 'detection',
    label: 'Detection',
    icon: ShieldAlert,
    items: [
      {
        id: 'alerts',
        label: 'Anomaly Queue',
        icon: ShieldAlert,
        blurb: 'Review suspicious behavioural patterns detected by Sentinel.',
        breadcrumb: ['Home', 'Detection', 'Anomaly Queue'],
      },
      {
        id: 'settings',
        label: 'Detection Policies',
        icon: Settings,
        blurb: 'Configure how Sentinel identifies and prioritizes suspicious behaviour.',
        breadcrumb: ['Home', 'Detection', 'Detection Policies'],
      },
    ],
  },
  {
    id: 'behaviour',
    label: 'Behaviour',
    icon: Users,
    items: [
      {
        id: 'behaviour',
        label: 'User Behaviour',
        icon: Users,
        blurb: 'Understand behavioural patterns and risk levels for individual users.',
        breadcrumb: ['Home', 'Behaviour', 'User Behaviour'],
      },
      {
        id: 'timeline',
        label: 'Activity Timeline',
        icon: Activity,
        blurb: 'Review chronological activity across users and systems.',
        breadcrumb: ['Home', 'Behaviour', 'Activity Timeline'],
      },
    ],
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    icon: BrainCircuit,
    items: [
      {
        id: 'models',
        label: 'Model Insights',
        icon: BrainCircuit,
        blurb: 'Understand how machine-learning models contribute to risk detection.',
        breadcrumb: ['Home', 'Intelligence', 'Model Insights'],
      },
    ],
  },
]

/* ── Helpers ───────────────────────────────────────────────────── */
export function navItem(id: ViewId): NavItem {
  for (const group of NAV_GROUPS) {
    const item = group.items.find((n) => n.id === id)
    if (item) return item
  }
  return NAV_GROUPS[0].items[0]
}

export function findGroup(id: ViewId): NavGroup | undefined {
  return NAV_GROUPS.find((g) => g.items.some((n) => n.id === id))
}
