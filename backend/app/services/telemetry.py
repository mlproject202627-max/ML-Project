"""Activity telemetry recorder — the single write path for security events.

Every meaningful employee action funnels through `record_event()`. It:

1. resolves request context (IP, approximate city/country, device),
2. derives sensitivity from the resource classification and severity from the
   event vocabulary,
3. writes one `Activity` row with fully structured columns,
4. appends an audit entry for security-relevant events, and
5. optionally hands the event to the detection engine.

Two invariants this module protects:

- **No secrets.** Passwords, tokens and API keys have no parameter here and
  must never be smuggled through `metadata`.
- **Never break the caller.** Banking operations call this on every request;
  a telemetry failure must degrade to a lost event, not a failed transfer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.activity import Activity, EVENT_SEVERITY, EVENT_TYPES
from app.models.device import Device, build_fingerprint
from app.models.resource import (
    Resource, CLASSIFICATION_RISK_WEIGHT, is_sensitive,
)
from app.models.audit_log import AuditLog, EMPLOYEE_ACTION, SENSITIVE_ACCESS, USB_EVENT, DOCUMENT_DOWNLOAD

logger = logging.getLogger("sentinel.telemetry")


# ---------------------------------------------------------------------------
# Action → event-type mapping
#
# The banking API calls this recorder with a business action label
# ("customer_search", "statement_download"). The spec's telemetry vocabulary is
# coarser, so labels are normalised here. The original label is preserved on
# Activity.action so nothing is lost.
# ---------------------------------------------------------------------------

ACTION_EVENT_MAP: dict[str, str] = {
    # Customer / account browsing
    "customer_search": "CUSTOMER_SEARCH",
    "customer_profile_view": "CUSTOMER_VIEW",
    "account_view": "ACCOUNT_VIEW",
    "account_list_view": "ACCOUNT_VIEW",
    "transaction_history_view": "TRANSACTION_VIEW",
    "transactions_view": "TRANSACTION_VIEW",
    "loans_view": "LOAN_VIEW",
    "loan_application_created": "LOAN_VIEW",
    "loan_status_changed": "LOAN_VIEW",
    "kyc_view": "CUSTOMER_VIEW",
    "kyc_status_changed": "SENSITIVE_DATA_ACCESS",
    "documents_view": "DOCUMENT_VIEW",
    "document_uploaded": "DOCUMENT_VIEW",
    "document_view": "DOCUMENT_VIEW",
    "document_download": "DOCUMENT_DOWNLOAD",
    "statement_download": "DOCUMENT_DOWNLOAD",
    "fund_transfer": "SENSITIVE_DATA_ACCESS",
    "sensitive_access": "SENSITIVE_DATA_ACCESS",
    "support_ticket_created": "INTERNAL_ACTION",
    "report_generated": "DOCUMENT_DOWNLOAD",
}

#: Actions that are security-relevant enough to also append an audit entry.
AUDITED_ACTIONS = {
    "fund_transfer", "kyc_status_changed", "loan_status_changed",
    "document_download", "statement_download", "sensitive_access",
    "document_uploaded",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def client_ip(request: Optional[Request]) -> Optional[str]:
    """Best-effort client IP, honouring the usual proxy header."""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def client_user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return (request.headers.get("user-agent") or "")[:512] or None


def describe_user_agent(ua: str) -> tuple[str, str]:
    """Very small UA reader → (browser, operating_system).

    Deliberately shallow: the demo records "a Chrome session on Windows", not a
    high-entropy fingerprint of an individual machine.
    """
    ua = ua or ""
    low = ua.lower()
    browser = "Unknown"
    for token, name in (
        ("edg/", "Edge"), ("opr/", "Opera"), ("chrome/", "Chrome"),
        ("firefox/", "Firefox"), ("safari/", "Safari"),
    ):
        if token in low:
            browser = name
            break
    os_name = "Unknown"
    for token, name in (
        ("windows", "Windows"), ("mac os", "macOS"), ("android", "Android"),
        ("iphone", "iOS"), ("ipad", "iOS"), ("linux", "Linux"),
    ):
        if token in low:
            os_name = name
            break
    return browser, os_name


# ---------------------------------------------------------------------------
# Device resolution
# ---------------------------------------------------------------------------

def resolve_device(db: Session, user, request: Optional[Request]) -> Optional[Device]:
    """Find or learn the device a request came from.

    The first sighting of a fingerprint creates the row with `is_new=True`;
    later sightings bump the counters and clear the new flag. This is what
    gives the NEW_DEVICE rule a trustworthy "have we seen this before?" signal.
    """
    ua = client_user_agent(request) or "unknown"
    browser, os_name = describe_user_agent(ua)
    platform = (request.headers.get("sec-ch-ua-platform") if request else None) or os_name
    fingerprint = build_fingerprint(ua, platform)

    device = (
        db.query(Device)
        .filter(Device.employee_id == user.id, Device.fingerprint == fingerprint)
        .first()
    )
    if device:
        device.last_seen = _now()
        device.seen_count = (device.seen_count or 0) + 1
        if (device.seen_count or 0) >= 3:
            device.is_new = False
            device.is_trusted = True
        return device

    device = Device(
        device_id=allocate_device_label(db, user),
        employee_id=user.id,
        label=f"{browser} on {os_name}",
        device_type="MOBILE" if os_name in ("Android", "iOS") else "WORKSTATION",
        operating_system=os_name,
        browser=browser,
        fingerprint=fingerprint,
        first_seen=_now(),
        last_seen=_now(),
        seen_count=1,
        is_trusted=False,
        is_new=True,
    )
    db.add(device)
    db.flush()
    return device


def allocate_device_label(db: Session, user) -> str:
    """A unique, human-readable device label for this employee.

    `Device.device_id` is globally unique, so the per-employee ordinal alone is
    not enough — every employee's first device would otherwise be `DEVICE-A1000`
    and the second employee to log in would hit a unique-constraint violation.
    The employee code makes the label unique while staying readable in the admin
    console.
    """
    existing = db.query(Device).filter(Device.employee_id == user.id).count()
    ordinal = f"{chr(ord('A') + min(existing, 25))}{1000 + existing}"
    owner = str(getattr(user, "employee_code", None) or str(user.id)[:8]).upper()
    # Keep the whole thing inside the 40-character column.
    return f"DEVICE-{owner[:24]}-{ordinal}"


def simulated_device(db: Session, user, label: str, *, browser: str = "Chrome",
                     operating_system: str = "Windows", is_new: bool = True) -> Device:
    """Register a device that did not arrive over HTTP (demo and simulation).

    Routes through the same table a real device would, so a scripted scenario
    exercises the genuine NEW_DEVICE path rather than asserting the flag itself.
    """
    device = db.query(Device).filter(Device.device_id == label).first()
    if device is not None:
        device.last_seen = _now()
        device.seen_count = (device.seen_count or 0) + 1
        return device

    device = Device(
        device_id=label,
        employee_id=user.id,
        label=f"{browser} on {operating_system}",
        device_type="WORKSTATION",
        operating_system=operating_system,
        browser=browser,
        fingerprint=build_fingerprint(f"simulated|{label}", operating_system),
        first_seen=_now(),
        last_seen=_now(),
        seen_count=1,
        is_trusted=not is_new,
        is_new=is_new,
    )
    db.add(device)
    db.flush()
    return device


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------

def normalise_event_type(action: str, explicit: Optional[str] = None) -> str:
    if explicit and explicit in EVENT_TYPES:
        return explicit
    if action in EVENT_TYPES:
        return action
    return ACTION_EVENT_MAP.get(action, "INTERNAL_ACTION")


def _baseline_for(db: Session, user):
    """The employee's baseline row, created on first contact.

    A missing baseline must not silently disable the after-hours and
    unusual-location signals, so this guarantees a row rather than returning
    None and letting the caller quietly skip those checks.
    """
    try:
        from app.services.baseline_service import get_or_create_baseline
        return get_or_create_baseline(db, user, commit=False)
    except Exception as exc:
        logger.warning("Could not resolve baseline for %s: %s", user.id, exc)
        return None


def _sensitivity_for(resource: Optional[Resource], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if resource is not None:
        return resource.classification or "INTERNAL"
    return "INTERNAL"


def _risk_for(sensitivity: str, severity: str) -> float:
    """Base risk contribution from classification, nudged by severity."""
    base = CLASSIFICATION_RISK_WEIGHT.get((sensitivity or "INTERNAL").upper(), 0.05)
    bump = {"LOW": 0.0, "MEDIUM": 0.05, "HIGH": 0.12, "CRITICAL": 0.20}.get((severity or "LOW").upper(), 0.0)
    return round(min(1.0, base + bump), 4)


def record_event(
    db: Session,
    *,
    user,
    action: str,
    event_type: Optional[str] = None,
    request: Optional[Request] = None,
    resource: Optional[Resource] = None,
    resource_label: Optional[str] = None,
    customer=None,
    device: Optional[Device] = None,
    device_label: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    sensitivity: Optional[str] = None,
    severity: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
    risk_contribution: Optional[float] = None,
    baseline=None,
    run_detection: bool = True,
    commit: bool = True,
) -> Activity:
    """Write one `Activity` row and (optionally) score it.

    Returns the persisted Activity. Never raises on detection failure — the
    telemetry row is the contract; scoring is best-effort.

    `baseline` may be supplied by bulk callers (the demo history generator) to
    avoid a lookup per event; when omitted it is resolved and created on demand.
    """
    action = (action or "unknown")[:255]
    etype = normalise_event_type(action, event_type)
    when = occurred_at or _now()

    # A live request gives us a device to learn from; seeded/backfilled events
    # carry a label instead. `device` lets the demo and simulator register a
    # device row so they exercise the same NEW_DEVICE path as a real client.
    device_row = resolve_device(db, user, request) if request is not None else device

    resolved_sensitivity = _sensitivity_for(resource, sensitivity)
    resolved_severity = severity or EVENT_SEVERITY.get(etype, "LOW")

    # Approximate location: prefer an explicit value, else fall back to the
    # user's branch city. Never precise coordinates.
    resolved_city = city or (user.branch_name or "").split(" ")[0] or None
    resolved_country = country or ("IN" if resolved_city else None)

    meta = dict(metadata or {})
    if baseline is None:
        baseline = _baseline_for(db, user)

    # Contextual flags the rules and the timeline both read.
    hour = when.hour + when.minute / 60.0
    if baseline is not None and not baseline.is_within_working_hours(hour):
        meta.setdefault("after_hours", True)
        if is_sensitive(resolved_sensitivity):
            meta.setdefault("after_hours_sensitive", True)

    if device_row is not None and device_row.is_new:
        meta.setdefault("new_device", True)

    if baseline is not None and resolved_city and not baseline.is_known_location(resolved_city, resolved_country):
        meta.setdefault("unusual_location", True)

    activity = Activity(
        user_id=user.id,
        timestamp=when,
        event_type=etype,
        action=action,
        resource=resource_label or (resource.name if resource else None),
        resource_id=resource.id if resource else None,
        customer_id=getattr(customer, "id", None),
        device_id=device_row.id if device_row else None,
        source_ip=client_ip(request),
        device=device_row.device_id if device_row else device_label,
        location=resolved_city,
        city=resolved_city,
        country=resolved_country,
        application="bank-portal",
        sensitivity=resolved_sensitivity,
        severity=resolved_severity,
        risk_contribution=risk_contribution if risk_contribution is not None else _risk_for(
            resolved_sensitivity, resolved_severity
        ),
        extra_metadata=meta,
    )
    db.add(activity)
    db.flush()

    # A device first seen right now is itself a security event worth recording.
    if device_row is not None and device_row.is_new and device_row.seen_count == 1:
        db.add(Activity(
            user_id=user.id,
            timestamp=when,
            event_type="NEW_DEVICE_DETECTED",
            action="new_device_detected",
            device=device_row.device_id,
            device_id=device_row.id,
            source_ip=client_ip(request),
            location=resolved_city,
            city=resolved_city,
            country=resolved_country,
            application="bank-portal",
            sensitivity="INTERNAL",
            severity=EVENT_SEVERITY.get("NEW_DEVICE_DETECTED", "MEDIUM"),
            risk_contribution=_risk_for("INTERNAL", "MEDIUM"),
            extra_metadata={"device_label": device_row.device_id, "browser": device_row.browser},
        ))
        db.flush()

    if action in AUDITED_ACTIONS or is_sensitive(resolved_sensitivity):
        db.add(AuditLog(
            actor_id=user.id,
            actor_code=getattr(user, "employee_code", None),
            actor_type="EMPLOYEE",
            action=DOCUMENT_DOWNLOAD if etype == "DOCUMENT_DOWNLOAD" else (
                USB_EVENT if etype.startswith("USB_") else SENSITIVE_ACCESS if is_sensitive(resolved_sensitivity) else EMPLOYEE_ACTION
            ),
            target_type="RESOURCE" if resource else ("CUSTOMER" if customer else "ACTIVITY"),
            target_id=str(resource.resource_id if resource else (getattr(customer, "customer_id", None) or activity.id)),
            description=f"{etype} — {resource_label or action}"[:500],
            ip_address=client_ip(request),
            request_id=(request.headers.get("x-request-id") if request else None),
            user_agent=client_user_agent(request),
            details={"sensitivity": resolved_sensitivity, "severity": resolved_severity},
        ))

    if commit:
        db.commit()
        db.refresh(activity)

    if run_detection:
        try:
            from app.services.detection import evaluate_activity
            evaluate_activity(db, user=user, activity=activity, commit=commit)
        except Exception as exc:  # detection must never break the caller
            logger.warning("Detection failed for activity %s: %s", activity.id, exc)
            try:
                db.rollback()
            except Exception:
                pass

    return activity
