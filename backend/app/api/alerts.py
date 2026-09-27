"""Alert queue and investigation workflow (spec §17, §19).

The analyst's side of the system: see what fired, why, start an investigation,
annotate it, close it out with a reason.

Two rules govern everything here:

- **Nothing is deleted.** Every transition annotates the alert and appends to
  `admin_actions` and `audit_logs`. A closed alert stays in the queue, filterable
  forever.
- **Every admin action is audited.** VIEW_ALERT, START_INVESTIGATION, ADD_NOTE,
  RESOLVE_ALERT and MARK_FALSE_POSITIVE all write an immutable record naming the
  administrator, the alert, the before/after status and the time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_security_analyst, require_security_read
from app.models.admin_action import (
    ADD_NOTE, MARK_FALSE_POSITIVE, RESOLVE_ALERT, START_INVESTIGATION, VIEW_ALERT,
    AdminAction,
)
from app.models.anomaly import (
    ACTIVE_ALERT_STATUSES, ALERT_STATUSES, LEGACY_STATUS_ALIASES, Anomaly,
)
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import (
    AlertDetailResponse, AlertListResponse, AlertNoteRequest, AlertResolveRequest,
    AlertSummary,
)

logger = logging.getLogger("sentinel.alerts")

router = APIRouter(prefix="/api/v1/admin", tags=["Alert Management"])

#: Why an alert exists, restated for the analyst rather than the log.
RULE_TITLES = {
    "RULE-001": "Access from an unusual location",
    "RULE-002": "Login outside normal hours",
    "RULE-003": "Activity from an unrecognised device",
    "RULE-004": "Excessive customer searches",
    "RULE-005": "Mass record access",
    "RULE-006": "Sensitive document download",
    "RULE-007": "After-hours sensitive access",
    "RULE-008": "Rapid sensitive resource access",
    "RULE-009": "Sensitive file transfer to removable media",
    "RULE-010": "Impossible-travel style anomaly",
    "RULE-011": "Multiple simultaneous anomalies",
    "BASELINE_DEVIATION": "Behavioural baseline deviation",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _audit(
    db: Session,
    *,
    admin: User,
    action: str,
    alert: Optional[Anomaly],
    description: str,
    details: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Append one admin action to both the action log and the audit trail."""
    db.add(AdminAction(
        admin_id=admin.id,
        admin_code=getattr(admin, "employee_code", None),
        alert_id=alert.id if alert else None,
        action=action,
        note=(details or {}).get("note"),
        previous_status=(details or {}).get("previousStatus"),
        new_status=(details or {}).get("newStatus"),
        details=details or {},
        ip_address=_client_ip(request),
        created_at=_now(),
    ))
    db.add(AuditLog(
        actor_id=admin.id,
        actor_code=getattr(admin, "employee_code", None),
        actor_type="ADMIN",
        action=action,
        target_type="ALERT" if alert else "SYSTEM",
        target_id=str(alert.id) if alert else None,
        description=description[:500],
        ip_address=_client_ip(request),
        request_id=request.headers.get("x-request-id") if request else None,
        user_agent=(request.headers.get("user-agent") or "")[:256] or None,
        details=details or {},
        created_at=_now(),
    ))


def _load_alert(db: Session, alert_id: str) -> Anomaly:
    alert = db.query(Anomaly).filter(Anomaly.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _summary(alert: Anomaly) -> AlertSummary:
    return AlertSummary(
        id=str(alert.id),
        employeeId=str(alert.user_id),
        employeeName=alert.user.name if alert.user else None,
        employeeCode=alert.user.employee_code if alert.user else None,
        department=alert.user.department if alert.user else None,
        severity=alert.severity,
        title=alert.title or (alert.description or "")[:120],
        description=alert.description,
        trigger=alert.trigger,
        riskScore=alert.risk_score,
        status=alert.normalised_status,
        detectedAt=alert.detected_at,
        resolvedAt=alert.resolved_at,
        createdAt=alert.created_at,
        detectionType=alert.detection_type,
        confidence=alert.confidence or 0.0,
    )


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

@router.get("/alerts", response_model=AlertListResponse)
def list_alerts(
    status: Optional[str] = Query(None, description="OPEN | INVESTIGATING | RESOLVED | FALSE_POSITIVE"),
    severity: Optional[str] = Query(None),
    employee_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("risk", description="risk | recent"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """The alert queue.

    Note the status filter is applied to the *normalised* vocabulary, so legacy
    rows written before the lifecycle existed still appear under the right tab.
    """
    query = db.query(Anomaly)

    if status:
        wanted = status.upper()
        if wanted not in ALERT_STATUSES:
            raise HTTPException(status_code=422, detail=f"Unknown status: {status}")
        # Include the legacy spellings that normalise onto this status, so a
        # row written before the lifecycle existed still lands in the right tab
        # rather than vanishing from every filter.
        raw = {wanted} | {
            legacy for legacy, current in LEGACY_STATUS_ALIASES.items() if current == wanted
        }
        query = query.filter(Anomaly.status.in_(raw))
    if severity:
        query = query.filter(Anomaly.severity == severity.upper())
    if employee_id:
        query = query.filter(Anomaly.user_id == employee_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.join(User, Anomaly.user_id == User.id).filter(
            User.name.ilike(like) | User.email.ilike(like) | Anomaly.title.ilike(like)
        )

    total = query.count()

    if sort == "recent":
        query = query.order_by(Anomaly.detected_at.desc())
    else:
        # Default: worst first, newest breaking ties.
        query = query.order_by(Anomaly.risk_score.desc(), Anomaly.detected_at.desc())

    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    counts = {
        row_status: count
        for row_status, count in db.query(Anomaly.status, func.count(Anomaly.id)).group_by(Anomaly.status).all()
    }
    # Present the counts under the current vocabulary even for legacy rows.
    normalised_counts: dict[str, int] = {}
    for row_status, count in counts.items():
        key = row_status if row_status in ALERT_STATUSES else LEGACY_STATUS_ALIASES.get(row_status, "OPEN")
        normalised_counts[key] = normalised_counts.get(key, 0) + count

    return AlertListResponse(
        items=[_summary(a) for a in rows],
        total=total,
        page=page,
        pageSize=page_size,
        counts=normalised_counts,
    )


@router.get("/alerts/{alert_id}", response_model=AlertDetailResponse)
def get_alert(
    alert_id: str,
    request: Request,
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """Full case file: the alert, why it fired, the employee's context, and the
    surrounding activity timeline."""
    alert = _load_alert(db, alert_id)
    employee = alert.user

    # Viewing a case is itself an auditable act — the employee's data was opened.
    _audit(
        db,
        admin=current_user,
        action=VIEW_ALERT,
        alert=alert,
        description=f"Opened alert {alert.title or alert.id} for review.",
        details={"severity": alert.severity, "riskScore": alert.risk_score},
        request=request,
    )
    db.commit()

    from app.models.activity import Activity
    from app.models.risk_score import RiskScore

    risk_history = (
        db.query(RiskScore)
        .filter(RiskScore.employee_id == alert.user_id)
        .order_by(RiskScore.timestamp.desc())
        .limit(50)
        .all()
    )
    timeline = (
        db.query(Activity)
        .filter(Activity.user_id == alert.user_id)
        .order_by(Activity.timestamp.desc())
        .limit(100)
        .all()
    )
    actions = (
        db.query(AdminAction)
        .filter(AdminAction.alert_id == alert.id)
        .order_by(AdminAction.created_at.asc())
        .all()
    )

    return AlertDetailResponse(
        alert=alert.to_dict(),
        employee={
            "id": str(employee.id),
            "name": employee.name,
            "email": employee.email,
            "employeeCode": employee.employee_code,
            "role": employee.roles[0].name if employee.roles else None,
            "department": employee.department,
            "jobTitle": employee.job_title,
            "branchName": employee.branch_name,
            "status": employee.status,
            "lastLogin": employee.last_login.isoformat() if employee.last_login else None,
        } if employee else {},
        baseline=employee.baseline.to_dict() if employee and employee.baseline else None,
        riskHistory=[
            {
                "score": r.current_score,
                "level": r.risk_level,
                "change": r.change,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "ruleScore": r.rule_score,
                "mlScore": r.ml_score,
                "baselineScore": r.baseline_score,
            }
            for r in reversed(risk_history)
        ],
        timeline=[a.to_dict() for a in reversed(timeline)],
        actions=[
            {
                "id": str(a.id),
                "action": a.action,
                "adminCode": a.admin_code,
                "note": a.note,
                "previousStatus": a.previous_status,
                "newStatus": a.new_status,
                "createdAt": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ],
    )


# ---------------------------------------------------------------------------
# Investigation transitions
# ---------------------------------------------------------------------------

@router.post("/alerts/{alert_id}/investigate", response_model=AlertSummary)
def start_investigation(
    alert_id: str,
    request: Request,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Move an OPEN alert into INVESTIGATING."""
    alert = _load_alert(db, alert_id)
    previous = alert.normalised_status

    if previous not in ACTIVE_ALERT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Alert is already closed as {previous}",
        )
    if previous == "INVESTIGATING":
        raise HTTPException(status_code=409, detail="Alert is already under investigation")

    alert.status = "INVESTIGATING"
    alert.updated_at = _now()

    _audit(
        db,
        admin=current_user,
        action=START_INVESTIGATION,
        alert=alert,
        description=f"Investigation started on alert {alert.title or alert.id}.",
        details={"previousStatus": previous, "newStatus": "INVESTIGATING"},
        request=request,
    )
    db.commit()
    db.refresh(alert)
    return _summary(alert)


@router.post("/alerts/{alert_id}/notes", response_model=AlertSummary)
def add_note(
    alert_id: str,
    payload: AlertNoteRequest,
    request: Request,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Append an investigator's note. Notes are additive; editing is not offered
    because the audit trail would then have two versions of events."""
    alert = _load_alert(db, alert_id)

    _audit(
        db,
        admin=current_user,
        action=ADD_NOTE,
        alert=alert,
        description=f"Investigation note added to alert {alert.title or alert.id}.",
        details={"note": payload.note, "previousStatus": alert.normalised_status,
                 "newStatus": alert.normalised_status},
        request=request,
    )
    db.commit()
    db.refresh(alert)
    return _summary(alert)


@router.post("/alerts/{alert_id}/resolve", response_model=AlertSummary)
def resolve_alert(
    alert_id: str,
    payload: AlertResolveRequest,
    request: Request,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Close an alert as RESOLVED (a real incident, handled) or FALSE_POSITIVE
    (looked at, benign). Either way the reason is mandatory."""
    alert = _load_alert(db, alert_id)
    previous = alert.normalised_status

    if previous not in ACTIVE_ALERT_STATUSES:
        raise HTTPException(status_code=409, detail=f"Alert is already closed as {previous}")

    outcome = (payload.outcome or "RESOLVED").upper()
    if outcome not in ("RESOLVED", "FALSE_POSITIVE"):
        raise HTTPException(status_code=422, detail="outcome must be RESOLVED or FALSE_POSITIVE")

    alert.status = outcome
    alert.resolved_at = _now()
    alert.resolved_by = current_user.id
    alert.resolution_reason = payload.resolutionReason
    alert.updated_at = _now()

    _audit(
        db,
        admin=current_user,
        action=RESOLVE_ALERT if outcome == "RESOLVED" else MARK_FALSE_POSITIVE,
        alert=alert,
        description=(
            f"Alert {alert.title or alert.id} marked {outcome}: {payload.resolutionReason}"
        )[:500],
        details={
            "note": payload.resolutionReason,
            "previousStatus": previous,
            "newStatus": outcome,
            "riskScore": alert.risk_score,
        },
        request=request,
    )
    db.commit()
    db.refresh(alert)
    return _summary(alert)


@router.post("/alerts/{alert_id}/false-positive", response_model=AlertSummary)
def mark_false_positive(
    alert_id: str,
    payload: AlertNoteRequest,
    request: Request,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Convenience wrapper over `resolve` for the common 'this was benign' case."""
    return resolve_alert(
        alert_id,
        AlertResolveRequest(resolutionReason=payload.note, outcome="FALSE_POSITIVE"),
        request,
        current_user,
        db,
    )
