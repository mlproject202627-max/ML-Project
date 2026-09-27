"""Simulated removable-media activity (spec §10).

    ⚠  SIMULATION ONLY — no endpoint is ever inspected.

Sentinel does not enumerate a real machine's USB bus, does not read a real
device's filesystem, and does not install an agent that could. The employee
portal offers an explicit "Simulate Device Activity" control, and the endpoint
agent (where one is used) reports only what the operating system already
surfaces to any user. Both paths land in the same `usb_events` table so the
detection engine sees a realistic, consent-safe stand-in.

Modelled sequence:

    CONNECT  →  TRANSFER (one row per file)  →  DISCONNECT

A transfer of CONFIDENTIAL material or above is recorded as
`SENSITIVE_FILE_TRANSFER`, which is what RULE-009 looks for.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import EMPLOYEE_ROLES, require_employee, role_names
from app.models.resource import CLASSIFICATIONS, Resource, is_sensitive
from app.models.usb_event import USB_ACTIONS, UsbEvent
from app.models.user import User
from app.schemas.simulation import (
    UsbActionResponse, UsbConnectRequest, UsbEventOut, UsbTransferRequest,
)

logger = logging.getLogger("sentinel.simulation")

router = APIRouter(prefix="/api/v1/simulation", tags=["Simulation"])

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")


def _clean_label(label: str) -> str:
    """Normalise a device label. Rejects rather than silently rewriting, so a
    malformed label cannot become a different device's identity."""
    candidate = (label or "").strip()
    if not _LABEL_RE.match(candidate):
        raise HTTPException(
            status_code=422,
            detail="deviceLabel must be 3–80 characters of letters, digits, dot, dash or underscore",
        )
    return candidate.upper()


def _to_out(event: UsbEvent) -> UsbEventOut:
    return UsbEventOut(
        id=str(event.id),
        deviceLabel=event.device_label,
        action=event.action,
        fileName=event.file_name,
        fileSize=event.file_size,
        classification=event.classification,
        resourceId=str(event.resource_id) if event.resource_id else None,
        occurredAt=event.occurred_at,
        notes=event.notes,
    )


def _load_resource(db: Session, ref: str) -> Optional[Resource]:
    """Resolve a resource by its human-readable id, then by primary key."""
    resource = db.query(Resource).filter(Resource.resource_id == ref).first()
    if resource is not None:
        return resource
    try:
        import uuid as _uuid

        return db.query(Resource).filter(Resource.id == _uuid.UUID(str(ref))).first()
    except (ValueError, AttributeError, TypeError):
        # Not a UUID and not a known resource id — a clean miss, not an error.
        return None


def _emit(
    db: Session,
    user: User,
    request: Request,
    *,
    action: str,
    device_label: str,
    event_type: str,
    resource: Optional[Resource] = None,
    metadata: Optional[dict] = None,
    severity: Optional[str] = None,
) -> None:
    """Mirror a simulated device action into the security timeline."""
    try:
        from app.services.telemetry import record_event
        record_event(
            db,
            user=user,
            action=action,
            event_type=event_type,
            request=request,
            resource=resource,
            device_label=device_label,
            severity=severity,
            metadata={"simulated": True, "deviceLabel": device_label, **(metadata or {})},
        )
    except Exception as exc:
        logger.warning("Could not record simulated %s for %s: %s", action, user.id, exc)
        try:
            db.rollback()
        except Exception:
            pass


@router.post("/usb/connect", response_model=UsbActionResponse)
def usb_connect(
    payload: UsbConnectRequest,
    request: Request,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Simulate attaching a removable device."""
    label = _clean_label(payload.deviceLabel)

    event = UsbEvent(
        employee_id=current_user.id,
        device_label=label,
        action="CONNECT",
        occurred_at=datetime.now(timezone.utc),
        notes="Simulated attach event (academic demonstration).",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    _emit(
        db, current_user, request,
        action="usb_connected",
        device_label=label,
        event_type="USB_CONNECTED",
        metadata={"usbEventId": str(event.id)},
    )
    return UsbActionResponse(
        event=_to_out(event),
        message=f"Simulated attach of {label} recorded.",
        flagged=False,
    )


@router.post("/usb/disconnect", response_model=UsbActionResponse)
def usb_disconnect(
    payload: UsbConnectRequest,
    request: Request,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Simulate detaching a removable device."""
    label = _clean_label(payload.deviceLabel)

    event = UsbEvent(
        employee_id=current_user.id,
        device_label=label,
        action="DISCONNECT",
        occurred_at=datetime.now(timezone.utc),
        notes="Simulated detach event (academic demonstration).",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    _emit(
        db, current_user, request,
        action="usb_disconnected",
        device_label=label,
        event_type="USB_DISCONNECTED",
        metadata={"usbEventId": str(event.id)},
    )
    return UsbActionResponse(
        event=_to_out(event),
        message=f"Simulated detach of {label} recorded.",
        flagged=False,
    )


@router.post("/usb/transfer", response_model=UsbActionResponse)
def usb_transfer(
    payload: UsbTransferRequest,
    request: Request,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Simulate copying a file to removable media.

    Transferring a registered resource requires entitlement to it — the
    simulation must not become a way to move data the employee could not
    otherwise open.
    """
    label = _clean_label(payload.deviceLabel)

    resource: Optional[Resource] = None
    classification = (payload.classification or "").upper() or None
    file_name = payload.fileName
    file_size = payload.fileSize

    if payload.resourceId:
        resource = _load_resource(db, payload.resourceId)
        if resource is None:
            raise HTTPException(status_code=404, detail="Resource not found")

        if not resource.allows(roles=role_names(current_user), department=current_user.department):
            raise HTTPException(
                status_code=403,
                detail="You do not have entitlement to transfer this resource",
            )

        classification = resource.classification
        file_name = file_name or resource.file_name
        file_size = file_size if file_size is not None else resource.file_size

    if not file_name:
        raise HTTPException(status_code=422, detail="Provide a resourceId or a fileName to transfer")

    if classification and classification not in CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail=f"Unknown classification: {classification}")

    event = UsbEvent(
        employee_id=current_user.id,
        device_label=label,
        action="TRANSFER",
        file_name=file_name[:255],
        file_size=file_size,
        classification=classification,
        resource_id=resource.id if resource else None,
        occurred_at=datetime.now(timezone.utc),
        notes=payload.notes or "Simulated file transfer (academic demonstration).",
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    sensitive = bool(classification and is_sensitive(classification))
    event_type = "SENSITIVE_FILE_TRANSFER" if sensitive else "FILE_TRANSFER_SIMULATED"

    _emit(
        db, current_user, request,
        action="sensitive_file_transfer" if sensitive else "file_transfer_simulated",
        device_label=label,
        event_type=event_type,
        resource=resource,
        severity="CRITICAL" if sensitive else "HIGH",
        metadata={
            "usbEventId": str(event.id),
            "fileName": file_name,
            "fileSize": file_size,
            "classification": classification,
        },
    )

    size_mb = f"{file_size / (1024 * 1024):.1f} MB" if file_size else "unknown size"
    return UsbActionResponse(
        event=_to_out(event),
        message=(
            f"Simulated transfer of {file_name} ({size_mb}, {classification or 'unclassified'}) "
            f"to {label} recorded."
            + (" This is a sensitive transfer and has been raised in the security console." if sensitive else "")
        ),
        flagged=sensitive,
    )


@router.get("/usb/events", response_model=list[UsbEventOut])
def my_usb_events(
    limit: int = 50,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """The caller's own simulated device history, newest first."""
    limit = max(1, min(limit, 200))
    rows = (
        db.query(UsbEvent)
        .filter(UsbEvent.employee_id == current_user.id)
        .order_by(UsbEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_out(e) for e in rows]
