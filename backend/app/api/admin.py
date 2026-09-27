"""Security operations console API (spec §14–§18).

    GET  /api/v1/admin/dashboard          cards + charts
    GET  /api/v1/admin/employees          monitored employees with live risk
    GET  /api/v1/admin/employees/{id}     one employee, in depth
    POST /api/v1/admin/employees/{id}/recompute   re-run detection on demand
    GET  /api/v1/admin/threats            security timeline (spec §16)
    GET  /api/v1/admin/audit-logs         immutable audit trail (spec §18)

Guards split by HTTP verb, not by route: reads take `require_security_read`
(analyst roles plus the read-only VIEWER), writes take
`require_security_analyst`. An employee calling `/api/v1/admin/...` is refused by
the server regardless of what the client renders. The audit log is **read-only
over HTTP**: there is no POST, PATCH or DELETE anywhere in this module that
touches `audit_logs`.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import EMPLOYEE_ROLES, require_security_analyst, require_security_read
from app.models.activity import Activity
from app.models.anomaly import ACTIVE_ALERT_STATUSES, Anomaly
from app.models.audit_log import (
    AuditLog, DEMO_HISTORY_GENERATED, DEMO_SCENARIO_RUN,
)
from app.models.risk_score import RISK_LEVELS, RiskScore
from app.models.user import User
from app.schemas.admin import (
    AuditLogEntry, AuditLogListResponse, EmployeeListResponse, EmployeeRiskSummary,
    TimelineEvent, TimelineResponse,
)

logger = logging.getLogger("sentinel.admin")

router = APIRouter(prefix="/api/v1/admin", tags=["Security Operations"])

#: Roles treated as monitored employees (the subjects of analysis). Aliased from
#: the role groups rather than restated, so this module cannot drift from the
#: authorisation rules that decide who may use the employee portal.
EMPLOYEE_ROLE_NAMES = EMPLOYEE_ROLES

#: How far back the dashboard looks.
CHART_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return _now()
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _day_key(dt: datetime) -> str:
    return _aware(dt).date().isoformat()


def _latest_risk_map(db: Session) -> dict[str, RiskScore]:
    """Most recent risk score per employee.

    Fetch-then-reduce rather than a `row_number()` window: the window form has
    to be joined back onto the ORM entity, which is fragile across SQLite and
    Postgres. At this scale (one row per scoring run, a handful of employees)
    the difference is immaterial, and this version cannot silently return the
    wrong row.
    """
    latest: dict[str, RiskScore] = {}
    for row in db.query(RiskScore).order_by(RiskScore.timestamp.desc()).all():
        key = str(row.employee_id)
        if key not in latest:
            latest[key] = row
    return latest


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def dashboard(
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """Cards and charts for the security overview (spec §14)."""
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    chart_start = now - timedelta(days=CHART_DAYS)

    employees = db.query(User).filter(User.status == "ACTIVE").all()
    monitored = [
        u for u in employees
        if {r.name for r in u.roles} & EMPLOYEE_ROLE_NAMES
    ]

    risk_map = _latest_risk_map(db)

    open_alerts = db.query(Anomaly).filter(Anomaly.status.in_(ACTIVE_ALERT_STATUSES)).all()
    critical_alerts = [a for a in open_alerts if a.severity == "CRITICAL"]
    threats_today = db.query(Anomaly).filter(Anomaly.detected_at >= today_start).count()

    sensitive_accesses = (
        db.query(Activity)
        .filter(Activity.timestamp >= chart_start, Activity.sensitivity.in_(
            ["CONFIDENTIAL", "HIGHLY_CONFIDENTIAL", "RESTRICTED"]
        ))
        .count()
    )
    usb_event_count = (
        db.query(Activity)
        .filter(Activity.timestamp >= chart_start, Activity.event_type.like("USB_%"))
        .count()
    )

    high_risk = [
        u for u in monitored
        if (risk_map.get(str(u.id)) and risk_map[str(u.id)].risk_level in ("HIGH", "CRITICAL"))
    ]

    # -- charts ------------------------------------------------------------
    window_events = (
        db.query(Activity)
        .filter(Activity.timestamp >= chart_start)
        .order_by(Activity.timestamp.asc())
        .all()
    )
    window_alerts = (
        db.query(Anomaly).filter(Anomaly.detected_at >= chart_start).all()
    )

    days = [(chart_start + timedelta(days=i)).date().isoformat() for i in range(CHART_DAYS + 1)]

    threats_by_day: dict[str, dict] = {d: {"date": d, "count": 0, "critical": 0, "high": 0} for d in days}
    for alert in window_alerts:
        key = _day_key(alert.detected_at)
        if key in threats_by_day:
            threats_by_day[key]["count"] += 1
            if alert.severity == "CRITICAL":
                threats_by_day[key]["critical"] += 1
            elif alert.severity == "HIGH":
                threats_by_day[key]["high"] += 1

    risk_distribution = {level: 0 for level in RISK_LEVELS}
    for employee in monitored:
        row = risk_map.get(str(employee.id))
        risk_distribution[row.risk_level if row else "LOW"] = (
            risk_distribution.get(row.risk_level if row else "LOW", 0) + 1
        )

    ranking = sorted(
        (
            {
                "id": str(u.id),
                "name": u.name,
                "employeeCode": u.employee_code,
                "department": u.department,
                "branchName": u.branch_name,
                "riskScore": risk_map[str(u.id)].current_score if str(u.id) in risk_map else 0.0,
                "riskLevel": risk_map[str(u.id)].risk_level if str(u.id) in risk_map else "LOW",
            }
            for u in monitored
        ),
        key=lambda r: r["riskScore"],
        reverse=True,
    )[:10]

    sensitive_by_class = Counter(
        e.sensitivity for e in window_events
        if e.sensitivity in ("CONFIDENTIAL", "HIGHLY_CONFIDENTIAL", "RESTRICTED")
    )

    login_anomalies = Counter()
    location_anomalies = Counter()
    usb_activity = {d: {"date": d, "count": 0, "sensitive": 0} for d in days}
    after_hours = Counter()
    for event in window_events:
        key = _day_key(event.timestamp)
        meta = event.extra_metadata or {}
        if event.event_type in ("LOGIN_FAILURE", "NEW_DEVICE_DETECTED"):
            login_anomalies[key] += 1
        if event.event_type == "LOCATION_ANOMALY" or meta.get("unusual_location"):
            location_anomalies[event.city or "Unknown"] += 1
        if event.event_type.startswith("USB_") or event.event_type == "SENSITIVE_FILE_TRANSFER":
            if key in usb_activity:
                usb_activity[key]["count"] += 1
                if event.event_type == "SENSITIVE_FILE_TRANSFER":
                    usb_activity[key]["sensitive"] += 1
        if meta.get("after_hours") or event.event_type == "AFTER_HOURS_ACCESS":
            after_hours[key] += 1

    return {
        "cards": {
            "activeEmployees": len(employees),
            "employeesMonitored": len(monitored),
            "threatsToday": threats_today,
            "criticalAlerts": len(critical_alerts),
            "openAlerts": len(open_alerts),
            "sensitiveAccesses": sensitive_accesses,
            "usbEvents": usb_event_count,
            "highRiskEmployees": len(high_risk),
        },
        "charts": {
            "threatsOverTime": [threats_by_day[d] for d in days],
            "riskDistribution": [
                {"level": level, "count": risk_distribution.get(level, 0)} for level in RISK_LEVELS
            ],
            "employeeRiskRanking": ranking,
            "sensitiveDataAccess": [
                {"classification": cls, "count": count}
                for cls, count in sensitive_by_class.most_common()
            ],
            "loginAnomalies": [
                {"date": d, "count": login_anomalies.get(d, 0)} for d in days
            ],
            "locationAnomalies": [
                {"city": city, "count": count} for city, count in location_anomalies.most_common(8)
            ],
            "usbActivity": [usb_activity[d] for d in days],
            "afterHoursActivity": [
                {"date": d, "count": after_hours.get(d, 0)} for d in days
            ],
        },
        "generatedAt": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

@router.get("/employees", response_model=EmployeeListResponse)
def list_employees(
    search: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """The monitored-employee roster, ranked by current risk."""
    query = db.query(User)

    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            User.name.ilike(like) | User.email.ilike(like) | User.employee_code.ilike(like)
        )
    if department:
        query = query.filter(User.department == department)

    employees = [
        u for u in query.order_by(User.name.asc()).all()
        if {r.name for r in u.roles} & EMPLOYEE_ROLE_NAMES
    ]

    risk_map = _latest_risk_map(db)
    alert_counts = dict(
        db.query(Anomaly.user_id, func.count(Anomaly.id))
        .filter(Anomaly.status.in_(ACTIVE_ALERT_STATUSES))
        .group_by(Anomaly.user_id)
        .all()
    )

    last_activity: dict[str, datetime] = dict(
        db.query(Activity.user_id, func.max(Activity.timestamp)).group_by(Activity.user_id).all()
    )

    items = []
    for employee in employees:
        row = risk_map.get(str(employee.id))
        level = row.risk_level if row else "LOW"
        if risk_level and level != risk_level.upper():
            continue
        items.append(EmployeeRiskSummary(
            id=str(employee.id),
            name=employee.name,
            email=employee.email,
            employeeCode=employee.employee_code,
            role=employee.roles[0].name if employee.roles else None,
            department=employee.department,
            jobTitle=employee.job_title,
            branchName=employee.branch_name,
            status=employee.status,
            riskScore=row.current_score if row else 0.0,
            riskLevel=level,
            riskChange=row.change if row else 0.0,
            openAlerts=alert_counts.get(employee.id, 0),
            lastActivityAt=last_activity.get(employee.id),
            lastLoginAt=employee.last_login,
        ))

    items.sort(key=lambda i: i.riskScore, reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    return EmployeeListResponse(
        items=items[start:start + page_size],
        total=total,
        page=page,
        pageSize=page_size,
    )


@router.get("/employees/{employee_id}")
def employee_detail(
    employee_id: str,
    days: int = Query(30, ge=1, le=180),
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """Everything the employee-monitoring view shows (spec §15).

    The activity window is fetched once and the per-section views (locations,
    devices, customers, downloads, USB) are derived from it in Python, so the
    page is one query rather than nine.
    """
    employee = db.query(User).filter(User.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    since = _now() - timedelta(days=days)
    events = (
        db.query(Activity)
        .filter(Activity.user_id == employee.id, Activity.timestamp >= since)
        .order_by(Activity.timestamp.desc())
        .limit(1000)
        .all()
    )

    risk_history = (
        db.query(RiskScore)
        .filter(RiskScore.employee_id == employee.id)
        .order_by(RiskScore.timestamp.asc())
        .limit(200)
        .all()
    )
    alerts = (
        db.query(Anomaly)
        .filter(Anomaly.user_id == employee.id)
        .order_by(Anomaly.detected_at.desc())
        .limit(50)
        .all()
    )

    locations = Counter(e.city for e in events if e.city)
    devices = Counter(e.device for e in events if e.device)
    customers: dict[str, int] = Counter()
    resources: Counter = Counter()
    downloads: list[dict] = []
    usb: list[dict] = []
    logins: list[dict] = []

    for event in events:
        if event.customer_id:
            customers[str(event.customer_id)] += 1
        if event.resource_id or event.resource:
            resources[event.resource or str(event.resource_id)] += 1
        if event.event_type == "DOCUMENT_DOWNLOAD":
            meta = event.extra_metadata or {}
            downloads.append({
                "resource": event.resource,
                "classification": event.sensitivity,
                "fileSize": meta.get("fileSize"),
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            })
        if event.event_type.startswith("USB_") or event.event_type == "SENSITIVE_FILE_TRANSFER":
            usb.append({
                "eventType": event.event_type,
                "device": event.device,
                "resource": event.resource,
                "classification": event.sensitivity,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            })
        if event.event_type in ("LOGIN_SUCCESS", "LOGIN_FAILURE"):
            logins.append({
                "eventType": event.event_type,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "ipAddress": event.source_ip,
                "city": event.city,
                "country": event.country,
                "device": event.device,
            })

    latest = risk_history[-1] if risk_history else None

    return {
        "employee": {
            "id": str(employee.id),
            "name": employee.name,
            "email": employee.email,
            "employeeCode": employee.employee_code,
            "role": employee.roles[0].name if employee.roles else None,
            "department": employee.department,
            "jobTitle": employee.job_title,
            "branchCode": employee.branch_code,
            "branchName": employee.branch_name,
            "status": employee.status,
            "lastLogin": employee.last_login.isoformat() if employee.last_login else None,
        },
        "risk": {
            "score": latest.current_score if latest else 0.0,
            "level": latest.risk_level if latest else "LOW",
            "change": latest.change if latest else 0.0,
            "reasons": (latest.reasons or []) if latest else [],
            "ruleScore": latest.rule_score if latest else 0.0,
            "mlScore": latest.ml_score if latest else 0.0,
            "baselineScore": latest.baseline_score if latest else 0.0,
            "timestamp": latest.timestamp.isoformat() if latest and latest.timestamp else None,
        },
        "riskHistory": [
            {
                "score": r.current_score,
                "level": r.risk_level,
                "change": r.change,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in risk_history
        ],
        "baseline": employee.baseline.to_dict() if employee.baseline else None,
        "loginHistory": logins[:50],
        "locationHistory": [{"city": c, "count": n} for c, n in locations.most_common(15)],
        "deviceHistory": [{"device": d, "count": n} for d, n in devices.most_common(15)],
        "customerAccess": [{"customerId": c, "count": n} for c, n in customers.most_common(25)],
        "resourceAccess": [{"resource": r, "count": n} for r, n in resources.most_common(25)],
        "downloads": downloads[:50],
        "usbEvents": usb[:50],
        "alerts": [a.to_dict() for a in alerts],
        "timeline": [e.to_dict() for e in events[:200]],
        "windowDays": days,
        "eventCount": len(events),
    }


@router.post("/employees/{employee_id}/recompute")
def recompute_employee(
    employee_id: str,
    request: Request,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Re-run baseline, rules, ML and risk for one employee on demand.

    Exposed so the demo can drive a scenario and immediately show the resulting
    assessment, and so an analyst can refresh a case without waiting for the
    next live event.
    """
    employee = db.query(User).filter(User.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    from app.services import baseline_service, detection

    baseline_service.recompute_baseline(db, employee, commit=True)
    result = detection.evaluate_employee(db, employee, commit=True)

    db.add(AuditLog(
        actor_id=current_user.id,
        actor_code=getattr(current_user, "employee_code", None),
        actor_type="ADMIN",
        action="RECOMPUTE_RISK",
        target_type="EMPLOYEE",
        target_id=str(employee.id),
        description=f"Detection re-run for {employee.name} → {result['assessment'].level}.",
        ip_address=(request.client.host if request.client else None),
        details={"score": result["assessment"].score, "level": result["assessment"].level},
        created_at=_now(),
    ))
    db.commit()

    assessment = result["assessment"]
    return {
        "employeeId": str(employee.id),
        "risk": assessment.to_dict(),
        "alert": result["alert"].to_dict() if result["alert"] else None,
        "ml": result["ml"].to_dict(),
        "baselineDeviation": result["baselineDeviation"],
        "contributions": result["contributions"],
        "featureVector": result["featureVector"],
        "eventsConsidered": result["eventsConsidered"],
    }


# ---------------------------------------------------------------------------
# Security timeline (spec §16)
# ---------------------------------------------------------------------------

@router.get("/threats", response_model=TimelineResponse)
def threat_timeline(
    employee_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    sensitivity: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """The chronological security timeline — the key demonstration view.

    Shows time, event, resource, employee, severity and risk contribution for
    every recorded action, newest first.
    """
    query = db.query(Activity)

    if employee_id:
        query = query.filter(Activity.user_id == employee_id)
    if event_type:
        query = query.filter(Activity.event_type == event_type)
    if severity:
        query = query.filter(Activity.severity == severity.upper())
    if sensitivity:
        query = query.filter(Activity.sensitivity == sensitivity.upper())
    if date_from:
        try:
            query = query.filter(Activity.timestamp >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=422, detail="date_from must be ISO 8601")
    if date_to:
        try:
            query = query.filter(Activity.timestamp <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(status_code=422, detail="date_to must be ISO 8601")

    total = query.count()
    rows = (
        query.order_by(Activity.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    names = {
        u.id: u for u in db.query(User).filter(User.id.in_({r.user_id for r in rows})).all()
    } if rows else {}

    items = []
    for row in rows:
        owner = names.get(row.user_id)
        items.append(TimelineEvent(
            id=str(row.id),
            timestamp=row.timestamp,
            eventType=row.event_type,
            action=row.action,
            employeeId=str(row.user_id),
            employeeName=owner.name if owner else None,
            employeeCode=owner.employee_code if owner else None,
            resource=row.resource,
            sensitivity=row.sensitivity,
            severity=row.severity,
            riskContribution=row.risk_contribution or 0.0,
            location=row.city or row.location,
            device=row.device,
            ipAddress=row.source_ip,
            metadata=row.extra_metadata or {},
        ))

    return TimelineResponse(items=items, total=total, page=page, pageSize=page_size)


# ---------------------------------------------------------------------------
# Audit log (spec §18)
# ---------------------------------------------------------------------------

@router.get("/audit-logs", response_model=AuditLogListResponse)
def audit_logs(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_security_read),
    db: Session = Depends(get_db),
):
    """Read the append-only audit trail.

    There is no write path in this module by design: rows are inserted by the
    services that perform the action, and nothing in the application issues an
    UPDATE or DELETE against this table.
    """
    query = db.query(AuditLog)

    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if date_from:
        try:
            query = query.filter(AuditLog.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(status_code=422, detail="date_from must be ISO 8601")
    if date_to:
        try:
            query = query.filter(AuditLog.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(status_code=422, detail="date_to must be ISO 8601")
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(AuditLog.description.ilike(like) | AuditLog.actor_code.ilike(like))

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogListResponse(
        items=[
            AuditLogEntry(
                id=str(row.id),
                actorId=str(row.actor_id) if row.actor_id else None,
                actorCode=row.actor_code,
                actorType=row.actor_type,
                action=row.action,
                targetType=row.target_type,
                targetId=row.target_id,
                description=row.description,
                ipAddress=row.ip_address,
                requestId=row.request_id,
                details=row.details or {},
                createdAt=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        pageSize=page_size,
    )


# ---------------------------------------------------------------------------
# Demo mode (spec §20, §26, §27)
#
# These endpoints are how a demonstration gets its data. They write synthetic
# activity under real employee identities, which is indistinguishable from a
# real incident unless it is labelled — so every call appends an explicit audit
# entry naming the operator who triggered it.
# ---------------------------------------------------------------------------

@router.post("/employees/{employee_id}/reset-risk")
def reset_employee_risk(
    employee_id: str,
    reason: Optional[str] = Query(None, description="Why the carried risk is being cleared"),
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Clear an employee's carried risk without deleting any history.

    Scores decay over 24 hours, so a reviewed employee stays elevated for the
    rest of the day. This appends a zero-score row and closes any active alert,
    leaving the earlier scores, alerts and audit entries intact.
    """
    from app.services import detection

    employee = db.query(User).filter(User.id == employee_id).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    return detection.reset_risk(db, employee, actor=current_user, reason=reason)


@router.get("/demo/scenarios")
def list_demo_scenarios(current_user: User = Depends(require_security_read)):
    """The scripted behaviours a demonstration can replay."""
    from app.utils.seed_scenarios import EMPLOYEE_PATTERNS, HISTORY_DAYS, SCENARIOS

    return {
        "scenarios": [
            {"name": name, "description": description}
            for name, description in SCENARIOS.items()
        ],
        "historyDays": HISTORY_DAYS,
        "employees": sorted(EMPLOYEE_PATTERNS.keys()),
    }


@router.post("/demo/scenario/{name}")
def run_demo_scenario(
    name: str,
    email: Optional[str] = Query(None, description="Employee to run the scenario against"),
    reset: bool = Query(
        True,
        description="Clear the employee's carried risk first, so the result is attributable to this scenario",
    ),
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Inject one scripted scenario and return the resulting detection state.

    The response carries a `progression` list so the UI can show risk climbing
    through LOW → MODERATE → HIGH → CRITICAL rather than appearing at its final
    value with no explanation of how it got there.
    """
    from app.utils.seed_scenarios import run_scenario

    try:
        result = run_scenario(db, name, email=email, reset=reset, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    db.add(AuditLog(
        actor_id=current_user.id,
        actor_code=current_user.employee_code,
        actor_type="ADMIN",
        action=DEMO_SCENARIO_RUN,
        target_type="EMPLOYEE",
        target_id=result["employee"]["id"],
        description=(
            f"Demo scenario '{result['scenario']}' executed against "
            f"{result['employee']['name']} by {current_user.name}."
        ),
        details={
            "scenario": result["scenario"],
            "employeeEmail": result["employee"]["email"],
            "resultingScore": result["risk"]["score"],
            "resultingLevel": result["risk"]["level"],
            "synthetic": True,
        },
    ))
    db.commit()

    result["synthetic"] = True
    result["executedBy"] = {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
    }
    return result


@router.post("/demo/history")
def generate_demo_history(
    days: int = Query(30, ge=7, le=90),
    force: bool = Query(False, description="Regenerate even if history already exists"),
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    """Generate the normal working history that baselines and the ML model need.

    Only meaningful on an empty database: without it no baseline can be derived
    and the Isolation Forest has nothing to train on.
    """
    from app.utils.seed_scenarios import seed_history

    written = seed_history(db, days=days, force=force)

    db.add(AuditLog(
        actor_id=current_user.id,
        actor_code=current_user.employee_code,
        actor_type="ADMIN",
        action=DEMO_HISTORY_GENERATED,
        target_type="SYSTEM",
        target_id="demo-history",
        description=(
            f"Demo history generation requested by {current_user.name} "
            f"({days} days) — {written} events written."
        ),
        details={"days": days, "eventsWritten": written, "force": force, "synthetic": True},
    ))
    db.commit()

    return {
        "days": days,
        "eventsWritten": written,
        "skipped": written == 0,
        "synthetic": True,
        "note": (
            "Existing history was sufficient; nothing generated."
            if written == 0
            else "History written and baselines recomputed."
        ),
    }
