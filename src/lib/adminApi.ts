import { apiFetch } from './api'

/* ------------------------------------------------------------------
   Security-console API client (spec §14–§19).

   Mirrors the shape of `bankApi.ts`: plain typed functions over
   `apiFetch`, one per endpoint, no caching and no global state. The
   server is the only source of truth for what an analyst may see —
   every route below is guarded server-side, and a VIEWER session that
   somehow rendered a write control still gets a 403 from FastAPI.

   Response fields are camelCase because the backend Pydantic schemas
   (`app/schemas/admin.py`) declare them that way. Nothing here renames
   or reshapes: mapping onto the UI's own domain model lives in
   `adapters.ts`, so a backend change breaks one file rather than nine.
------------------------------------------------------------------ */

const BASE = '/api/v1/admin'

export type RiskLevel = 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'CRITICAL'
export type AlertStatus = 'OPEN' | 'INVESTIGATING' | 'RESOLVED' | 'FALSE_POSITIVE'
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const s = search.toString()
  return s ? `?${s}` : ''
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export interface DashboardCards {
  activeEmployees: number
  employeesMonitored: number
  threatsToday: number
  criticalAlerts: number
  openAlerts: number
  sensitiveAccesses: number
  usbEvents: number
  highRiskEmployees: number
}

export interface ThreatPoint {
  date: string
  /** Detections raised on this day. */
  count: number
  critical: number
  high: number
}

export interface RiskDistributionPoint {
  level: string
  count: number
}

export interface EmployeeRiskRanking {
  id: string
  name: string
  employeeCode?: string | null
  department?: string | null
  branchName?: string | null
  riskScore: number
  riskLevel: string
}

export interface ClassificationCount {
  classification: string
  count: number
}

export interface DateCount {
  date: string
  count: number
}

export interface CityCount {
  city: string
  count: number
}

export interface AdminDashboard {
  cards: DashboardCards
  charts: {
    threatsOverTime: ThreatPoint[]
    riskDistribution: RiskDistributionPoint[]
    employeeRiskRanking: EmployeeRiskRanking[]
    sensitiveDataAccess: ClassificationCount[]
    loginAnomalies: DateCount[]
    locationAnomalies: CityCount[]
    usbActivity: ThreatPoint[]
    afterHoursActivity: DateCount[]
  }
}

export function getAdminDashboard(days = 14): Promise<AdminDashboard> {
  return apiFetch(`${BASE}/dashboard${qs({ days })}`)
}

/* ------------------------------------------------------------------ */
/* Employees                                                           */
/* ------------------------------------------------------------------ */

export interface EmployeeRiskSummary {
  id: string
  name: string
  email: string
  employeeCode?: string | null
  role?: string | null
  department?: string | null
  jobTitle?: string | null
  branchName?: string | null
  status: string
  riskScore: number
  riskLevel: string
  riskChange: number
  openAlerts: number
  lastActivityAt?: string | null
  lastLoginAt?: string | null
}

export interface EmployeeListResponse {
  items: EmployeeRiskSummary[]
  total: number
  page: number
  pageSize: number
}

export function listEmployees(params?: {
  search?: string
  department?: string
  risk_level?: string
  page?: number
  page_size?: number
}): Promise<EmployeeListResponse> {
  return apiFetch(`${BASE}/employees${qs(params ?? {})}`)
}

/** Everything the employee-monitoring view shows, assembled server-side. */
export interface EmployeeDetail {
  employee: {
    id: string
    name: string
    email: string
    employeeCode?: string | null
    role?: string | null
    department?: string | null
    jobTitle?: string | null
    branchCode?: string | null
    branchName?: string | null
    status: string
    lastLogin?: string | null
  }
  risk: {
    score: number
    level: string
    change: number
    reasons: string[]
    ruleScore: number
    mlScore: number
    baselineScore: number
    timestamp?: string | null
  }
  riskHistory: { score: number; level: string; change: number; timestamp?: string | null }[]
  alerts: AlertSummary[]
  activity: TimelineEvent[]
  locations: { city: string; count: number }[]
  devices: { device: string; count: number }[]
  customers: { customer: string; count: number }[]
  downloads: { resource: string; count: number }[]
  usbEvents: { device: string; count: number }[]
  baseline?: Record<string, unknown> | null
  statistics: Record<string, number>
}

export function getEmployeeDetail(employeeId: string, days = 30): Promise<EmployeeDetail> {
  return apiFetch(`${BASE}/employees/${employeeId}${qs({ days })}`)
}

/** Re-run the full detection pass for one employee. Writes a risk row. */
export function recomputeEmployee(employeeId: string, days = 7): Promise<Record<string, unknown>> {
  return apiFetch(`${BASE}/employees/${employeeId}/recompute${qs({ days })}`, { method: 'POST' })
}

/** Zero an employee's *carried* risk. Appends a risk row; erases nothing. */
export function resetEmployeeRisk(employeeId: string, reason?: string): Promise<Record<string, unknown>> {
  return apiFetch(`${BASE}/employees/${employeeId}/reset-risk${qs({ reason })}`, { method: 'POST' })
}

/* ------------------------------------------------------------------ */
/* Alert queue and investigation (spec §17, §19)                        */
/* ------------------------------------------------------------------ */

export interface AlertSummary {
  id: string
  employeeId: string
  employeeName?: string | null
  employeeCode?: string | null
  department?: string | null
  severity: string
  title: string
  description?: string | null
  trigger?: string | null
  riskScore: number
  status: string
  detectedAt?: string | null
  resolvedAt?: string | null
  createdAt?: string | null
  /** Rule family that raised it — `RULE-007`, `ISOLATION_FOREST`, … */
  detectionType?: string | null
  confidence?: number
}

export interface AlertListResponse {
  items: AlertSummary[]
  total: number
  page: number
  pageSize: number
  /** Counts per status across the whole table, not just the current page. */
  counts: Record<string, number>
}

export function listAlerts(params?: {
  status?: string
  severity?: string
  employee_id?: string
  search?: string
  sort?: 'risk' | 'recent'
  page?: number
  page_size?: number
}): Promise<AlertListResponse> {
  return apiFetch(`${BASE}/alerts${qs(params ?? {})}`)
}

export interface RuleHitDict {
  ruleId: string
  name: string
  severity: string
  /** Contribution on the 0–100 risk scale. */
  risk: number
  explanation: string
  evidence?: Record<string, unknown>
  eventIds?: string[]
}

/**
 * The full `Anomaly.to_dict()` — what the *detail* endpoint returns. Strictly
 * richer than `AlertSummary`: it carries the rule hits and the evidence dict
 * the queue projection omits.
 */
export interface AnomalyDict {
  id: string
  employeeId: string
  employeeName?: string | null
  employeeCode?: string | null
  department?: string | null
  detectionType?: string | null
  severity: string
  title?: string | null
  description?: string | null
  trigger?: string | null
  riskScore: number
  anomalyScore?: number
  mlAnomalyScore?: number | null
  baselineDeviation?: number | null
  confidence: number
  ruleHits: RuleHitDict[]
  evidence: Record<string, unknown>
  status: string
  detectedAt?: string | null
  createdAt?: string | null
  resolvedAt?: string | null
  resolvedBy?: string | null
  resolutionReason?: string | null
}

export interface AlertAction {
  id: string
  action: string
  adminCode?: string | null
  note?: string | null
  previousStatus?: string | null
  newStatus?: string | null
  createdAt?: string | null
}

export interface AlertEmployee {
  id: string
  name: string
  email?: string | null
  employeeCode?: string | null
  role?: string | null
  department?: string | null
  jobTitle?: string | null
  branchName?: string | null
  status?: string | null
  lastLogin?: string | null
}

export interface AlertDetail {
  alert: AnomalyDict
  /** Empty object when the subject identity could not be loaded. */
  employee: AlertEmployee | Record<string, never>
  baseline?: Record<string, unknown> | null
  riskHistory: {
    score: number
    level: string
    change: number
    timestamp?: string | null
    ruleScore?: number
    mlScore?: number
    baselineScore?: number
  }[]
  timeline: TimelineEvent[]
  /** Every investigation transition, oldest first. Append-only. */
  actions: AlertAction[]
}

export function getAlertDetail(alertId: string): Promise<AlertDetail> {
  return apiFetch(`${BASE}/alerts/${alertId}`)
}

/* -- lifecycle transitions ----------------------------------------- */

export function startInvestigation(alertId: string): Promise<AlertSummary> {
  return apiFetch(`${BASE}/alerts/${alertId}/investigate`, { method: 'POST' })
}

export function addAlertNote(alertId: string, note: string): Promise<AlertSummary> {
  return apiFetch(`${BASE}/alerts/${alertId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

/** Close an alert. The reason is mandatory server-side — an unexplained
 *  closure is not a record an investigator can defend later. */
export function resolveAlert(
  alertId: string,
  resolutionReason: string,
  outcome: 'RESOLVED' | 'FALSE_POSITIVE' = 'RESOLVED',
): Promise<AlertSummary> {
  return apiFetch(`${BASE}/alerts/${alertId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ resolutionReason, outcome }),
  })
}

export function markAlertFalsePositive(alertId: string, note: string): Promise<AlertSummary> {
  return apiFetch(`${BASE}/alerts/${alertId}/false-positive`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

/* ------------------------------------------------------------------ */
/* Security timeline (spec §16) and audit trail (spec §18)              */
/* ------------------------------------------------------------------ */

export interface TimelineEvent {
  id: string
  timestamp?: string | null
  eventType: string
  action: string
  employeeId: string
  employeeName?: string | null
  employeeCode?: string | null
  resource?: string | null
  sensitivity?: string | null
  severity?: string | null
  riskContribution: number
  location?: string | null
  device?: string | null
  ipAddress?: string | null
  metadata?: Record<string, unknown>
}

export interface TimelineResponse {
  items: TimelineEvent[]
  total: number
  page: number
  pageSize: number
}

export function getThreatTimeline(params?: {
  employee_id?: string
  event_type?: string
  severity?: string
  sensitivity?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}): Promise<TimelineResponse> {
  return apiFetch(`${BASE}/threats${qs(params ?? {})}`)
}

export interface AuditLogEntry {
  id: string
  actorId?: string | null
  actorCode?: string | null
  actorType: string
  action: string
  targetType?: string | null
  targetId?: string | null
  description?: string | null
  ipAddress?: string | null
  requestId?: string | null
  details: Record<string, unknown>
  createdAt?: string | null
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  total: number
  page: number
  pageSize: number
}

/** Read-only. There is deliberately no create/update/delete counterpart. */
export function getAuditLogs(params?: {
  actor_id?: string
  action?: string
  target_type?: string
  date_from?: string
  date_to?: string
  search?: string
  page?: number
  page_size?: number
}): Promise<AuditLogListResponse> {
  return apiFetch(`${BASE}/audit-logs${qs(params ?? {})}`)
}

/* ------------------------------------------------------------------ */
/* Demonstration control (spec §21)                                    */
/* ------------------------------------------------------------------ */

export interface DemoScenario {
  name: string
  description: string
}

export interface DemoScenariosResponse {
  scenarios: DemoScenario[]
  historyDays: number
  employees: string[]
}

export function listDemoScenarios(): Promise<DemoScenariosResponse> {
  return apiFetch(`${BASE}/demo/scenarios`)
}

export function runDemoScenario(
  name: string,
  opts?: { email?: string; reset?: boolean },
): Promise<Record<string, unknown>> {
  return apiFetch(`${BASE}/demo/scenario/${encodeURIComponent(name)}${qs(opts ?? {})}`, {
    method: 'POST',
  })
}

export function generateDemoHistory(days = 30): Promise<Record<string, unknown>> {
  return apiFetch(`${BASE}/demo/history${qs({ days })}`, { method: 'POST' })
}
