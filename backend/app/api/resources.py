"""Classified resource registry API (spec §5, §6, §24).

The employee-facing half of the sensitive-resource system: browse what you are
entitled to see, open it, download it. Every open and every download writes a
security event, which is what feeds the rules, the ML model and the admin
timeline.

Access control is enforced *here*, on the server, by consulting
`Resource.allows()` — not by hiding a button in the UI. Changing the URL of a
resource you are not entitled to returns 403 regardless of what the client
believes its role to be (spec §24, "Employee A must not access Employee B's
restricted resource just by changing the URL").
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    ADMIN_ROLES, EMPLOYEE_ROLES, require_employee, require_staff, role_names,
)
from app.models.resource import (
    Resource, CLASSIFICATIONS, SENSITIVE_CLASSIFICATIONS, classification_rank, is_sensitive,
)
from app.models.user import User
from app.schemas.resource import (
    ResourceAccessResponse, ResourceDetail, ResourceListResponse, ResourceSummary,
)

logger = logging.getLogger("sentinel.resources")

router = APIRouter(prefix="/api/v1/resources", tags=["Sensitive Resources"])


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _summary(resource: Resource) -> ResourceSummary:
    return ResourceSummary(
        id=str(resource.id),
        resourceId=resource.resource_id,
        name=resource.name,
        resourceType=resource.resource_type,
        classification=resource.classification,
        owner=resource.owner,
        ownerDepartment=resource.owner_department,
        customerId=resource.customer_id and str(resource.customer_id),
        fileName=resource.file_name,
        fileSize=resource.file_size,
        mime=resource.mime,
        downloadable=bool(resource.downloadable),
        sensitive=is_sensitive(resource.classification),
        createdAt=resource.created_at.isoformat() if resource.created_at else None,
    )


def _detail(resource: Resource) -> ResourceDetail:
    base = _summary(resource)
    return ResourceDetail(
        **base.model_dump(),
        allowedRoles=resource.role_list(),
        allowedDepartments=resource.department_list(),
        riskWeight=classification_rank(resource.classification),
    )


def _load(db: Session, resource_ref: str) -> Resource:
    """Look a resource up by its human-readable id, falling back to the PK."""
    resource = db.query(Resource).filter(Resource.resource_id == resource_ref).first()
    if resource is None:
        try:
            resource = db.query(Resource).filter(Resource.id == resource_ref).first()
        except Exception:
            resource = None
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


def _assert_can_access(resource: Resource, user: User) -> None:
    """Server-side entitlement check. Raises 403 rather than returning nothing."""
    roles = role_names(user)
    if roles & ADMIN_ROLES:
        # Security staff may review the registry while investigating, but they
        # cannot *act* as an employee (see `require_employee` on the write
        # endpoints below).
        return
    if not resource.allows(roles=roles, department=user.department):
        raise HTTPException(
            status_code=403,
            detail="You do not have entitlement to this resource",
        )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

@router.get("", response_model=ResourceListResponse)
def list_resources(
    classification: Optional[str] = Query(None, description="Filter by classification"),
    resource_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    only_sensitive: bool = Query(False),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """List the resources this caller is entitled to see.

    The list itself is filtered by entitlement, so an employee cannot even
    enumerate the existence of restricted material.
    """
    roles = role_names(current_user)
    is_security = bool(roles & ADMIN_ROLES)

    query = db.query(Resource)
    if classification:
        if classification not in CLASSIFICATIONS:
            raise HTTPException(status_code=422, detail=f"Unknown classification: {classification}")
        query = query.filter(Resource.classification == classification)
    if resource_type:
        query = query.filter(Resource.resource_type == resource_type)
    if only_sensitive:
        query = query.filter(Resource.classification.in_(sorted(SENSITIVE_CLASSIFICATIONS)))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(Resource.name.ilike(like) | Resource.resource_id.ilike(like))

    rows = query.order_by(Resource.classification.desc(), Resource.name.asc()).all()

    visible = [r for r in rows if is_security or r.allows(roles=roles, department=current_user.department)]
    return ResourceListResponse(
        items=[_summary(r) for r in visible],
        total=len(visible),
        withheld=len(rows) - len(visible),
    )


@router.get("/{resource_ref}", response_model=ResourceDetail)
def get_resource(
    resource_ref: str,
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    """Resource metadata. Entitlement is enforced before anything is returned."""
    resource = _load(db, resource_ref)
    _assert_can_access(resource, current_user)
    return _detail(resource)


# ---------------------------------------------------------------------------
# Employee actions — these generate telemetry
# ---------------------------------------------------------------------------

def _record(db: Session, user: User, request: Request, resource: Resource, action: str, event_type: str) -> None:
    """Write the access event. Failure to record must not fail the request."""
    try:
        from app.services.telemetry import record_event
        record_event(
            db,
            user=user,
            action=action,
            event_type=event_type,
            request=request,
            resource=resource,
            metadata={
                "resourceCode": resource.resource_id,
                "resourceType": resource.resource_type,
                "classification": resource.classification,
                "fileName": resource.file_name,
                "fileSize": resource.file_size,
            },
        )
    except Exception as exc:
        logger.warning("Could not record %s on %s: %s", event_type, resource.resource_id, exc)
        try:
            db.rollback()
        except Exception:
            pass


@router.post("/{resource_ref}/access", response_model=ResourceAccessResponse)
def access_resource(
    resource_ref: str,
    request: Request,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Open a resource. Emits DOCUMENT_VIEW, or SENSITIVE_DATA_ACCESS above
    CONFIDENTIAL — the distinction the rules and the ML features rely on."""
    resource = _load(db, resource_ref)
    _assert_can_access(resource, current_user)

    event_type = "SENSITIVE_DATA_ACCESS" if is_sensitive(resource.classification) else "DOCUMENT_VIEW"
    _record(db, current_user, request, resource, "sensitive_access", event_type)

    return ResourceAccessResponse(
        resource=_summary(resource),
        eventType=event_type,
        recordedAt=datetime.now(timezone.utc).isoformat(),
        message=(
            f"Access to {resource.classification} material recorded in the security audit trail."
            if is_sensitive(resource.classification)
            else "Access recorded."
        ),
    )


@router.post("/{resource_ref}/download", response_model=ResourceAccessResponse)
def download_resource(
    resource_ref: str,
    request: Request,
    current_user: User = Depends(require_employee),
    db: Session = Depends(get_db),
):
    """Download a resource. Emits DOCUMENT_DOWNLOAD with the byte size attached,
    so the ML `download_volume` feature has something real to measure."""
    resource = _load(db, resource_ref)
    _assert_can_access(resource, current_user)

    if not resource.downloadable:
        raise HTTPException(status_code=403, detail="This resource is view-only and cannot be downloaded")

    _record(db, current_user, request, resource, "document_download", "DOCUMENT_DOWNLOAD")

    return ResourceAccessResponse(
        resource=_summary(resource),
        eventType="DOCUMENT_DOWNLOAD",
        recordedAt=datetime.now(timezone.utc).isoformat(),
        message=(
            f"Download of {resource.classification} material recorded. "
            f"Transfers of this classification are reviewed by the security team."
            if is_sensitive(resource.classification)
            else "Download recorded."
        ),
    )
