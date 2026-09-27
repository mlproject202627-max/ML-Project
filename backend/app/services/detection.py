"""Detection orchestrator (spec §12, §13, §17, §19).

The seam where the three signals meet and an alert is born:

    Activity event
        ├─► Rule engine        (11 deterministic rules, → explainable hits)
        ├─► Baseline service   (deviation from this employee's own normal)
        └─► Isolation Forest   (statistical outlier score)
                    ↓
              Risk engine      (0–100 score, 5 bands, decaying)
                    ↓
              ThreatAlert      (created or refreshed, never duplicated)

Called from `services.telemetry.record_event` after every significant event,
and on demand from the admin API.

Alert discipline:

- One *active* alert per employee. Re-scoring refreshes it rather than stacking
  a new row on every event, so an incident reads as one case in the queue.
- Nothing is ever deleted. The alert row is updated in place; the decision
  history lives in `audit_logs`.
- Detection failures are logged, never raised into the request path.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.activity import Activity, EVENT_SEVERITY
from app.models.anomaly import Anomaly, ACTIVE_ALERT_STATUSES
from app.models.audit_log import AuditLog, ALERT_CREATED, RESET_RISK, RISK_CHANGE
from app.models.risk_score import RiskScore, level_for_score
from app.models.user import User
from app.services import baseline_service, risk as risk_engine
from ml import anomaly as anomaly_model
from ml import rule_engine

logger = logging.getLogger("sentinel.detection")

#: Score at which an employee acquires an alert in the queue.
ALERT_THRESHOLD = 41.0  # ELEVATED and above

#: Monitoring window for rules and feature extraction.
WINDOW_HOURS = 24

#: Event types worth scoring. Everything is still *recorded*; low-signal
#: housekeeping (support tickets, preference changes) simply does not trigger a
#: detection pass, which keeps the request path cheap.
SCORED_EVENT_TYPES = {
    "LOGIN_SUCCESS", "LOGIN_FAILURE", "LOGOUT",
    "CUSTOMER_SEARCH", "CUSTOMER_VIEW", "ACCOUNT_VIEW", "TRANSACTION_VIEW", "LOAN_VIEW",
    "DOCUMENT_VIEW", "DOCUMENT_DOWNLOAD", "SENSITIVE_DATA_ACCESS",
    "USB_CONNECTED", "USB_DISCONNECTED", "FILE_TRANSFER_SIMULATED", "SENSITIVE_FILE_TRANSFER",
    "AFTER_HOURS_ACCESS", "NEW_DEVICE_DETECTED", "LOCATION_ANOMALY",
}

#: Risk level → alert severity.
LEVEL_TO_SEVERITY = {
    "LOW": "LOW",
    "MODERATE": "LOW",
    "ELEVATED": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------

def evaluate_employee(
    db: Session,
    user: User,
    *,
    now: Optional[datetime] = None,
    commit: bool = True,
) -> dict:
    """Run every detector for one employee and persist the resulting risk score.

    Returns the assessment as a dict. Raises nothing the caller must handle —
    the API layer decides whether to surface a failure.
    """
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(hours=WINDOW_HOURS)

    baseline = baseline_service.get_or_create_baseline(db, user, commit=False)

    # 1. Deterministic rules over the trailing window.
    events = rule_engine.collect_events(db, employee_id=user.id, window_hours=WINDOW_HOURS, now=now)
    rule_hits = rule_engine.evaluate(db, user=user, window_hours=WINDOW_HOURS, now=now, events=events)

    # 2. Isolation Forest on the same window.
    from ml.features import extract_features, resource_department_map

    vector = extract_features(
        events,
        baseline=baseline,
        resource_departments=resource_department_map(db, events),
        now=now,
    )
    ml_result = anomaly_model.detect(vector)
    contributions = ml_result.contributions or vector.top_contributors(
        reference=_reference_vector(baseline)
    )

    # 3. Deviation from this employee's own normal.
    deviation, deviation_components = baseline_service.baseline_deviation(
        db, user, window_start=window_start, window_end=now, baseline=baseline
    )

    # 4. Fuse.
    assessment = risk_engine.assess(
        db,
        employee_id=user.id,
        rule_hits=rule_hits,
        ml_score_raw=ml_result.score if ml_result.available else None,
        ml_available=ml_result.available,
        baseline_score=deviation,
        now=now,
        window_start=window_start,
        window_end=now,
        persist=commit,
    )

    if commit:
        _record_risk_change(db, user, assessment)

    alert = None
    if assessment.score >= ALERT_THRESHOLD:
        alert = sync_alert(
            db,
            user,
            assessment=assessment,
            ml_result=ml_result,
            deviation=deviation,
            deviation_components=deviation_components,
            contributions=contributions,
            now=now,
            commit=commit,
        )

    return {
        "assessment": assessment,
        "alert": alert,
        "ml": ml_result,
        "baselineDeviation": deviation,
        "baselineComponents": deviation_components,
        "contributions": contributions,
        "featureVector": vector.to_dict(),
        "eventsConsidered": len(events),
    }


def _reference_vector(baseline) -> "FeatureVector":
    """The employee's own baseline expressed as a feature vector, for lift ranking."""
    from ml.features import FeatureVector

    if baseline is None:
        return FeatureVector()
    return FeatureVector(
        login_hour=float(baseline.avg_login_hour or 0.0),
        records_accessed=float(baseline.avg_daily_accesses or 0.0),
        sensitive_records_accessed=float(baseline.avg_sensitive_accesses or 0.0),
        downloads=float(baseline.avg_downloads or 0.0),
        unique_customers=float(baseline.avg_unique_customers or 0.0),
        unique_resources=float(baseline.avg_unique_resources or 0.0),
        session_duration=float(baseline.typical_session_minutes or 0.0),
    )


# ---------------------------------------------------------------------------
# Activity-triggered evaluation
# ---------------------------------------------------------------------------

def evaluate_activity(db: Session, *, user: User, activity: Activity, commit: bool = True) -> Optional[dict]:
    """Score after one event. Skips low-signal event types."""
    if activity.event_type not in SCORED_EVENT_TYPES:
        return None
    try:
        return evaluate_employee(db, user, now=_aware(activity.timestamp), commit=commit)
    except Exception as exc:
        logger.warning("Detection pass failed for employee %s: %s", user.id, exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None


# ---------------------------------------------------------------------------
# Alert lifecycle
# ---------------------------------------------------------------------------

def active_alert_for(db: Session, employee_id) -> Optional[Anomaly]:
    return (
        db.query(Anomaly)
        .filter(Anomaly.user_id == employee_id, Anomaly.status.in_(ACTIVE_ALERT_STATUSES))
        .order_by(Anomaly.detected_at.desc())
        .first()
    )


def _build_title(user: User, assessment, hits) -> str:
    if not hits:
        return f"Elevated behavioural risk — {user.name}"
    top = max(hits, key=lambda h: h.risk)
    return f"{top.name} — {user.name}"


def _build_description(user: User, assessment, hits, ml_score: float, deviation: float) -> str:
    lines = [
        f"Risk score {assessment.score:.0f}/100 ({assessment.level}) for "
        f"{user.name} ({user.employee_code or user.email}), {user.job_title or 'employee'} "
        f"in {user.department or 'unknown department'}."
    ]
    if hits:
        lines.append(f"{len(hits)} detection rule(s) fired:")
        for hit in sorted(hits, key=lambda h: -h.risk)[:5]:
            lines.append(f"  • [{hit.rule_id}] {hit.explanation}")
    if ml_score > 0:
        lines.append(f"ML anomaly score: {ml_score:.0f}/100.")
    if deviation > 0:
        lines.append(f"Deviation from personal baseline: {deviation:.0f}/100.")
    return "\n".join(lines)[:4000]


def sync_alert(
    db: Session,
    user: User,
    *,
    assessment,
    ml_result=None,
    deviation: float = 0.0,
    deviation_components: Optional[dict] = None,
    contributions: Optional[list] = None,
    now: Optional[datetime] = None,
    commit: bool = True,
) -> Anomaly:
    """Create or refresh the employee's active alert.

    Refreshing rather than appending keeps one incident as one queue entry. A
    genuinely new alert is only opened once the previous one is resolved.
    """
    now = now or datetime.now(timezone.utc)
    hits = assessment.rule_hits
    severity = LEVEL_TO_SEVERITY.get(assessment.level, "MEDIUM")
    title = _build_title(user, assessment, hits)
    description = _build_description(
        user, assessment, hits, assessment.ml_score, assessment.baseline_score
    )
    trigger = " + ".join(h.rule_id for h in hits) or "BASELINE_DEVIATION"

    evidence = {
        "reasons": assessment.reasons,
        "baselineDeviation": assessment.baseline_score,
        "baselineComponents": deviation_components or {},
        "topContributors": contributions or [],
        "riskComponents": {
            "rule": assessment.rule_score,
            "ml": assessment.ml_score,
            "baseline": assessment.baseline_score,
        },
    }

    alert = active_alert_for(db, user.id)
    created = alert is None

    if created:
        alert = Anomaly(
            user_id=user.id,
            activity_id=None,
            detection_type=hits[0].rule_id if hits else "BASELINE_DEVIATION",
            severity=severity,
            title=title[:255],
            description=description[:1000],
            risk_score=assessment.score,
            anomaly_score=round(assessment.score / 100.0, 4),
            confidence=round(min(0.95, 0.5 + len(hits) * 0.1), 3),
            ml_anomaly_score=assessment.ml_score or None,
            baseline_deviation=assessment.baseline_score or None,
            trigger=trigger[:500],
            rule_hits=[h.to_dict() for h in hits],
            evidence=evidence,
            status="OPEN",
            detected_at=now,
        )
        db.add(alert)
        db.flush()
    else:
        alert.severity = severity
        alert.title = title[:255]
        alert.description = description[:1000]
        alert.risk_score = assessment.score
        alert.anomaly_score = round(assessment.score / 100.0, 4)
        alert.ml_anomaly_score = assessment.ml_score or None
        alert.baseline_deviation = assessment.baseline_score or None
        alert.trigger = trigger[:500]
        alert.rule_hits = [h.to_dict() for h in hits]
        alert.evidence = evidence
        alert.updated_at = now

    if commit:
        db.commit()
        db.refresh(alert)
        if created:
            _record_alert_created(db, user, alert)

    return alert


# ---------------------------------------------------------------------------
# Audit + telemetry of detection outcomes
# ---------------------------------------------------------------------------

def _record_risk_change(db: Session, user: User, assessment) -> None:
    """Append an audit entry whenever the risk level actually moves."""
    previous_level = level_for_score(assessment.previous_score) if assessment.previous_score else None
    if previous_level == assessment.level:
        return
    db.add(AuditLog(
        actor_id=user.id,
        actor_code=getattr(user, "employee_code", None),
        actor_type="SYSTEM",
        action=RISK_CHANGE,
        target_type="EMPLOYEE",
        target_id=str(user.id),
        description=(
            f"Risk level {previous_level or 'NONE'} → {assessment.level} "
            f"(score {assessment.score:.0f}/100)."
        ),
        details={
            "score": assessment.score,
            "previousScore": assessment.previous_score,
            "level": assessment.level,
            "previousLevel": previous_level,
            "rules": [h.rule_id for h in assessment.rule_hits],
        },
    ))
    try:
        db.commit()
    except Exception as exc:
        logger.warning("Could not write risk-change audit entry: %s", exc)
        db.rollback()


def _record_alert_created(db: Session, user: User, alert: Anomaly) -> None:
    """Mirror a new alert into the audit log and the activity timeline."""
    now = datetime.now(timezone.utc)
    db.add(AuditLog(
        actor_id=user.id,
        actor_code=getattr(user, "employee_code", None),
        actor_type="SYSTEM",
        action=ALERT_CREATED,
        target_type="ALERT",
        target_id=str(alert.id),
        description=f"{alert.severity} alert opened: {alert.title}",
        details={
            "severity": alert.severity,
            "riskScore": alert.risk_score,
            "trigger": alert.trigger,
        },
        created_at=now,
    ))
    db.add(Activity(
        user_id=user.id,
        timestamp=now,
        event_type="THREAT_ALERT_CREATED",
        action="threat_alert_created",
        resource=alert.title,
        severity=EVENT_SEVERITY.get("THREAT_ALERT_CREATED", "CRITICAL"),
        sensitivity="INTERNAL",
        risk_contribution=0.0,
        application="sentinel-detection",
        extra_metadata={
            "alertId": str(alert.id),
            "trigger": alert.trigger,
            "riskScore": alert.risk_score,
        },
    ))
    try:
        db.commit()
    except Exception as exc:
        logger.warning("Could not mirror alert %s into the timeline: %s", alert.id, exc)
        db.rollback()


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def risk_snapshot(db: Session, user: User) -> dict:
    """Current risk state without re-running detection (for dashboards)."""
    latest = risk_engine.latest_risk_score(db, user.id)
    if latest is None:
        return {
            "score": 0.0, "level": "LOW", "reasons": [], "timestamp": None,
            "ruleScore": 0.0, "mlScore": 0.0, "baselineScore": 0.0, "change": 0.0,
        }
    return {
        "score": latest.current_score,
        "level": latest.risk_level,
        "reasons": latest.reasons or [],
        "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
        "ruleScore": latest.rule_score,
        "mlScore": latest.ml_score,
        "baselineScore": latest.baseline_score,
        "change": latest.change,
    }


def risk_history(db: Session, employee_id, *, limit: int = 200) -> list[RiskScore]:
    return (
        db.query(RiskScore)
        .filter(RiskScore.employee_id == employee_id)
        .order_by(RiskScore.timestamp.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Operator override
# ---------------------------------------------------------------------------

#: Recorded on the zero-score row an operator override appends.
RESET_NOTE = "Risk state cleared by operator"


def reset_risk(db: Session, user: User, *, actor=None, reason: Optional[str] = None,
               commit: bool = True) -> dict:
    """Clear an employee's *carried* risk without deleting any history.

    Scores decay over 24 hours by design, so an employee assessed HIGH stays
    elevated for the rest of the day even once the behaviour stops. An analyst
    who has reviewed the activity and wants to assess what happens next needs a
    way to say so — and a demonstration needs the same thing, or replaying a
    scenario against a previously-used employee inherits the old score and the
    outcome says nothing about the scenario.

    Nothing is deleted. A zero-score row is appended (so the trend line shows
    the operator's intervention), any active alert is closed as RESOLVED with
    the given reason, and both moves are audited against the operator.
    """
    now = datetime.now(timezone.utc)
    previous = risk_engine.latest_risk_score(db, user.id)
    previous_score = previous.current_score if previous else 0.0

    closed = None
    alert = active_alert_for(db, user.id)
    if alert is not None:
        alert.status = "RESOLVED"
        alert.resolved_at = now
        alert.resolved_by = getattr(actor, "id", None)
        alert.resolution_reason = reason or RESET_NOTE
        alert.updated_at = now
        closed = str(alert.id)

    row = RiskScore(
        employee_id=user.id,
        current_score=0.0,
        previous_score=previous_score,
        change=round(-(previous_score or 0.0), 2),
        risk_level="LOW",
        reasons=[f"Risk state cleared: {reason or RESET_NOTE}"],
        rule_score=0.0,
        ml_score=0.0,
        baseline_score=0.0,
        window_start=now - timedelta(hours=WINDOW_HOURS),
        window_end=now,
        timestamp=now,
        note=RESET_NOTE,
    )
    db.add(row)

    db.add(AuditLog(
        actor_id=getattr(actor, "id", None),
        actor_code=getattr(actor, "employee_code", None),
        actor_type="ADMIN" if actor is not None else "SYSTEM",
        action=RESET_RISK,
        target_type="EMPLOYEE",
        target_id=str(user.id),
        description=(
            f"Risk state cleared for {user.name} "
            f"({user.employee_code or user.email}); previous score {previous_score:.0f}/100."
        ),
        details={
            "previousScore": previous_score,
            "closedAlert": closed,
            "reason": reason or RESET_NOTE,
        },
        created_at=now,
    ))

    if commit:
        db.commit()
    return {"previousScore": previous_score, "closedAlert": closed}
