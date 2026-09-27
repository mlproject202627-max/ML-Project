/* ------------------------------------------------------------------
   API → UI domain adapters.

   The console's components were written against the shapes in
   `data/types.ts` (lowercase severities, a `kind` from a fixed
   taxonomy, `headline`/`narrative`). The backend speaks its own
   vocabulary (`CRITICAL`, `RULE-007`, `title`/`description`).

   Translating in one place rather than in nine components means a
   backend rename breaks this file and nothing else. It is also the only
   place where the two taxonomies are reconciled, which is where that
   reconciliation should be argued about.
------------------------------------------------------------------ */
import type {
  ActivityEvent,
  Alert,
  AlertStatus,
  AnomalyKind,
  ContributingFactor,
  Severity,
} from '../data/types'
import type { AlertDetail, AlertSummary, AnomalyDict, TimelineEvent } from './adminApi'

/* -- vocabulary ---------------------------------------------------- */

export function severityFromApi(value: string | null | undefined): Severity {
  switch ((value ?? '').toUpperCase()) {
    case 'CRITICAL':
      return 'critical'
    case 'HIGH':
      return 'high'
    case 'MEDIUM':
      return 'medium'
    default:
      return 'low'
  }
}

/**
 * Map the backend lifecycle onto the four statuses the queue filters by.
 *
 * `RESOLVED` becomes `contained` rather than `dismissed`: the two are not the
 * same finding, and collapsing them would erase the distinction between "this
 * was real and we dealt with it" and "this was never real".
 */
export function statusFromApi(value: string | null | undefined): AlertStatus {
  switch ((value ?? '').toUpperCase()) {
    case 'OPEN':
    case 'NEW':
      return 'new'
    case 'INVESTIGATING':
    case 'IN_REVIEW':
    case 'ASSIGNED':
    case 'ESCALATED':
      return 'investigating'
    case 'RESOLVED':
    case 'CONTAINED':
    case 'CLOSED':
      return 'contained'
    case 'FALSE_POSITIVE':
    case 'DISMISSED':
      return 'dismissed'
    default:
      return 'new'
  }
}

/** The inverse, for sending a filter back to the API. */
export function statusToApi(value: AlertStatus | 'all'): string | undefined {
  switch (value) {
    case 'new':
      return 'OPEN'
    case 'investigating':
      return 'INVESTIGATING'
    case 'contained':
      return 'RESOLVED'
    case 'dismissed':
      return 'FALSE_POSITIVE'
    default:
      return undefined
  }
}

/**
 * Rule family → queue classification.
 *
 * The backend's `detection_type` is a rule id (`RULE-009`) or a detector name;
 * the UI groups by behaviour family. Most rules land somewhere obvious. Two do
 * not: there is no existing family for material leaving the estate, and none
 * for the correlation rule, so those were added to the taxonomy rather than
 * filed under the nearest wrong label.
 *
 * An unrecognised detection type falls back to `peer_deviation` — the
 * statistical-outlier family — because that is what an unexplained flag is.
 * The row still shows the real rule name from `detector`, so nothing is hidden.
 */
export function kindFromDetectionType(detectionType: string | null | undefined): AnomalyKind {
  const key = (detectionType ?? '').toUpperCase()
  switch (key) {
    case 'RULE-001': // unusual location
      return 'session_anomaly'
    case 'RULE-002': // unusual login time
    case 'RULE-007': // after-hours sensitive access
      return 'off_hours_access'
    case 'RULE-003': // new device
      return 'session_anomaly'
    case 'RULE-004': // excessive customer searches
    case 'RULE-008': // rapid sensitive resource access
      return 'resource_sweeping'
    case 'RULE-005': // mass record access
      return 'lateral_movement'
    case 'RULE-006': // sensitive document download
    case 'RULE-009': // transfer to removable media
      return 'data_exfiltration'
    case 'RULE-010': // impossible travel
      return 'impossible_travel'
    case 'RULE-011': // multiple simultaneous anomalies
      return 'correlated_anomaly'
    default:
      return 'peer_deviation'
  }
}

/** "Meera Krishnan" → "MK"; tolerates single names and stray whitespace. */
export function initialsFromName(name: string | null | undefined): string {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '??'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/* -- alerts -------------------------------------------------------- */

/**
 * A queue row.
 *
 * `factors` is deliberately empty here: the list projection does not carry the
 * rule hits, and inventing them from the title would put fabricated
 * corroboration in front of an analyst. `AlertDrawer` fills them from
 * `getAlertDetail`, which does.
 */
export function alertFromApi(row: AlertSummary | AnomalyDict): Alert {
  return {
    id: row.id,
    employeeId: row.employeeId,
    kind: kindFromDetectionType(row.detectionType),
    severity: severityFromApi(row.severity),
    confidence: row.confidence ?? 0,
    riskScore: Math.round(row.riskScore),
    detectedAt: row.detectedAt ?? row.createdAt ?? new Date().toISOString(),
    status: statusFromApi(row.status),
    headline: row.title || 'Unnamed detection',
    narrative: row.description || row.trigger || '',
    tactic: '',
    // `trigger` is the model's own one-line "what fired" — the closest thing
    // the backend has to the queue's short asset column.
    asset: row.trigger || '',
    sourceIp: '',
    geo: '',
    factors: [],
    detector: row.detectionType || 'sentinel',
    employeeName: row.employeeName ?? undefined,
    employeeDepartment: row.department ?? undefined,
    employeeInitials: initialsFromName(row.employeeName),
  }
}

export function alertsFromApi(rows: AlertSummary[]): Alert[] {
  return rows.map(alertFromApi)
}

/** The extra fields the detail endpoint carries that the queue does not. */
export interface AlertEnrichment {
  factors: ContributingFactor[]
  sourceIp: string
  geo: string
  detector: string
  /** Every rule that contributed, in the backend's own words. */
  ruleHits: AnomalyDict['ruleHits']
}

/**
 * Read the rule hits out of an alert detail response.
 *
 * `risk` is the rule's contribution on the 0–100 scale; `FactorBars` wants a
 * 0–1 weight, so the bars are scaled against the largest contributor rather
 * than against 100 — otherwise a lone 14-point rule renders as a barely
 * visible sliver and the panel looks empty.
 */
export function enrichmentFromDetail(detail: AlertDetail): AlertEnrichment {
  const alert = detail.alert
  const ruleHits = alert?.ruleHits ?? []

  const peak = ruleHits.reduce((max, h) => Math.max(max, h.risk ?? 0), 0) || 1
  const factors: ContributingFactor[] = ruleHits.map((h) => ({
    label: h.name || h.ruleId,
    weight: (h.risk ?? 0) / peak,
    detail: h.explanation,
  }))

  const evidence = alert?.evidence ?? {}
  const employee = detail.employee ?? {}

  return {
    factors,
    sourceIp: String(evidence.ipAddress ?? evidence.sourceIp ?? ''),
    // Approximate city/country only — the system is not permitted to hold
    // precise location, so this is what the telemetry actually recorded.
    geo: String(evidence.city ?? evidence.location ?? ('branchName' in employee ? employee.branchName ?? '' : '')),
    detector: alert?.detectionType || 'sentinel',
    ruleHits,
  }
}

/* -- timeline ------------------------------------------------------ */

/**
 * A telemetry event for the activity feed.
 *
 * `verdict` is derived from the persisted severity rather than recomputed:
 * the risk engine already decided how serious this event was, and a second
 * opinion computed in the browser would be a different answer to the same
 * question.
 */
export function activityFromTimeline(event: TimelineEvent): ActivityEvent {
  const severity = (event.severity ?? '').toUpperCase()
  const verdict: ActivityEvent['verdict'] =
    severity === 'CRITICAL' || severity === 'HIGH'
      ? 'suspicious'
      : severity === 'MEDIUM' || event.riskContribution >= 30
        ? 'notable'
        : 'normal'

  return {
    id: event.id,
    employeeId: event.employeeId,
    ts: event.timestamp ?? new Date().toISOString(),
    action: event.action || event.eventType,
    target: event.resource || event.eventType,
    verdict,
    risk: Math.round(event.riskContribution ?? 0),
    employeeName: event.employeeName ?? undefined,
    employeeInitials: initialsFromName(event.employeeName),
  }
}

export function activityFromTimelineList(events: TimelineEvent[]): ActivityEvent[] {
  return events.map(activityFromTimeline)
}
