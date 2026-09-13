/* ------------------------------------------------------------------
   Domain model for the Sentinel insider-threat UI.
   The focus is user behaviour / access anomalies, so every entity
   ultimately resolves to a person deviating from their peer group.
------------------------------------------------------------------ */

export type Severity = 'critical' | 'high' | 'medium' | 'low'

export type AnomalyKind =
  | 'off_hours_access'
  | 'lateral_movement'
  | 'peer_deviation'
  | 'privilege_escalation'
  | 'impossible_travel'
  | 'dormant_revival'
  | 'resource_sweeping'
  | 'session_anomaly'

export type AlertStatus = 'new' | 'investigating' | 'contained' | 'dismissed'

export type Department =
  | 'Engineering'
  | 'Finance'
  | 'IT Ops'
  | 'Sales'
  | 'HR'
  | 'Legal'
  | 'Product'
  | 'Support'
  | 'Executive'
  | 'Contract'

/** The six behavioural axes drawn on the employee radar. */
export interface BehaviourVector {
  /** Raw volume of records/resources touched vs. peer median */
  accessVolume: number
  /** Share of activity inside the 22:00–06:00 window */
  offHours: number
  /** Breadth of distinct systems/shares touched */
  resourceBreadth: number
  /** Use of elevated / admin entitlements */
  privilegeUse: number
  /** Statistical distance from the peer-group centroid */
  peerDeviation: number
  /** Travel speed between consecutive access geolocations */
  geoVelocity: number
}

export type BehaviourAxis = keyof BehaviourVector

/** A single named contributor behind an alert's score. */
export interface ContributingFactor {
  label: string
  /** 0–1 normalised influence on the final anomaly score */
  weight: number
  /** Human-readable observed value, e.g. "03:41 local vs 09:15 baseline" */
  detail: string
}

export interface Alert {
  id: string
  employeeId: string
  kind: AnomalyKind
  severity: Severity
  /** Model confidence 0–1 */
  confidence: number
  /** Composite risk score 0–100 */
  riskScore: number
  /** ISO timestamp of the triggering access */
  detectedAt: string
  status: AlertStatus
  headline: string
  narrative: string
  /** MITRE ATT&CK-ish tactic label for analyst context */
  tactic: string
  asset: string
  sourceIp: string
  geo: string
  factors: ContributingFactor[]
  /** Model that raised it */
  detector: string
}

export interface Employee {
  id: string
  name: string
  initials: string
  title: string
  department: Department
  /** Peer group used as the behavioural baseline */
  peerGroup: string
  /** 0–100 composite risk */
  riskScore: number
  /** Signed drift from the personal baseline, in standard deviations */
  drift: number
  behaviour: BehaviourVector
  /** 24 hourly activity intensities, each 0–100, for the mini heatmap */
  hourly: number[]
  lastSeen: string
  location: string
  tenureMonths: number
  openAlerts: number
  status: 'watchlist' | 'monitored' | 'cleared'
  baselineShift: { label: string; baseline: string; current: string; delta: string }[]
}

export interface TrendPoint {
  label: string
  anomalies: number
  meanRisk: number
  baseline: number
}

export interface HeatCell {
  /** 0 = Monday */
  day: number
  hour: number
  intensity: number
}

export interface ActivityEvent {
  id: string
  employeeId: string
  ts: string
  action: string
  target: string
  verdict: 'normal' | 'notable' | 'suspicious'
  risk: number
}

export interface DetectorHealth {
  name: string
  family: string
  status: 'healthy' | 'degraded' | 'training'
  precision: number
  recall: number
  f1: number
  auc: number
  drift: number
  lastTrained: string
  features: number
  throughput: string
}

export interface KindMeta {
  label: string
  short: string
  color: string
  description: string
}
