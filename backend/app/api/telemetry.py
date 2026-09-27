"""Real-time telemetry ingestion + retrieval.

Two ingestion paths:
- POST /api/v1/telemetry/browser — the Sentinel UI reports what the browser can
  genuinely observe: login/logout time, geolocation, file uploads/drops, paired
  USB attach, view dwell, heartbeats.
- POST /api/v1/telemetry/agent   — the native endpoint daemon reports OS-level
  USB plug/mount and file-watch events, authenticated with X-Agent-Key.

Both require a real user identity; demo data has no place here.
"""
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_admin
from app.core.agent_auth import get_agent_user, issue_agent_key
from app.models.user import User
from app.models.telemetry import TelemetryEvent
from app.models.agent_key import AgentKey
from app.schemas.telemetry import (
    TelemetryBatchIn, TelemetryEventOut, TelemetryIngestResult,
    TelemetryEventIn, AgentKeyCreate, AgentKeyOut, AgentKeyListItem,
    VALID_EVENT_TYPES,
)

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _store_event(db: Session, user_id, evt: TelemetryEventIn, ip: str) -> None:
    db.add(TelemetryEvent(
        user_id=user_id,
        event_type=evt.event_type,
        source=evt.source,
        occurred_at=evt.occurred_at,
        ip_address=evt.ip_address or ip,
        location=evt.location,
        latitude=evt.latitude,
        longitude=evt.longitude,
        accuracy_m=evt.accuracy_m,
        device=evt.device,
        resource=evt.resource,
        application=evt.application,
        event_metadata=evt.metadata,
        risk_contribution=evt.risk_contribution,
    ))


@router.post("/browser", response_model=TelemetryIngestResult)
def ingest_browser_telemetry(
    batch: TelemetryBatchIn,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ingest telemetry captured by the Sentinel web client for the signed-in user."""
    stored, rejected, errors = 0, 0, []
    ip = _client_ip(request)

    for evt in batch.events:
        if evt.event_type not in VALID_EVENT_TYPES:
            rejected += 1
            errors.append(f"Unknown event_type: {evt.event_type}")
            continue
        if evt.source not in ("browser", "agent"):
            rejected += 1
            errors.append(f"Invalid source: {evt.source}")
            continue
        _store_event(db, current_user.id, evt, ip)
        stored += 1

    db.commit()
    return TelemetryIngestResult(received=len(batch.events), stored=stored, rejected=rejected, errors=errors[:10])


@router.post("/agent", response_model=TelemetryIngestResult)
def ingest_agent_telemetry(
    batch: TelemetryBatchIn,
    request: Request,
    agent_user: User = Depends(get_agent_user),
    db: Session = Depends(get_db),
):
    """Ingest OS-level telemetry from an endpoint agent (USB plug, file watch)."""
    stored, rejected, errors = 0, 0, []
    ip = _client_ip(request)

    for evt in batch.events:
        if evt.event_type not in VALID_EVENT_TYPES:
            rejected += 1
            errors.append(f"Unknown event_type: {evt.event_type}")
            continue
        if evt.source != "agent":
            evt = evt.model_copy(update={"source": "agent"})
        _store_event(db, agent_user.id, evt, ip)
        stored += 1

    db.commit()
    return TelemetryIngestResult(received=len(batch.events), stored=stored, rejected=rejected, errors=errors[:10])


@router.get("", response_model=list[TelemetryEventOut])
def list_telemetry(
    user_id: Optional[str] = Query(None, description="Filter by monitored user"),
    event_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read telemetry (analyst+). Non-admins see only their own events."""
    from app.core.dependencies import require_security_analyst  # role names shared
    user_roles = {r.name for r in current_user.roles}
    query = db.query(TelemetryEvent)

    if "ADMIN" not in user_roles and not user_roles & {"SECURITY_MANAGER", "SECURITY_ANALYST"}:
        # plain users may inspect only their own telemetry
        query = query.filter(TelemetryEvent.user_id == current_user.id)
    elif user_id:
        query = query.filter(TelemetryEvent.user_id == user_id)

    if event_type:
        query = query.filter(TelemetryEvent.event_type == event_type)
    if source:
        query = query.filter(TelemetryEvent.source == source)

    total = query.count()
    offset = (page - 1) * page_size
    rows = query.order_by(TelemetryEvent.occurred_at.desc()).offset(offset).limit(page_size).all()

    results = []
    for e in rows:
        results.append(TelemetryEventOut(
            id=str(e.id),
            user_id=str(e.user_id),
            event_type=e.event_type,
            source=e.source,
            occurred_at=e.occurred_at,
            received_at=e.received_at,
            ip_address=e.ip_address,
            location=e.location,
            latitude=e.latitude,
            longitude=e.longitude,
            accuracy_m=e.accuracy_m,
            device=e.device,
            resource=e.resource,
            application=e.application,
            metadata=e.event_metadata or {},
            risk_contribution=e.risk_contribution,
        ))
    return results


# ---------------------------------------------------------------------------
# Admin: agent key management
# ---------------------------------------------------------------------------

@router.post("/agent-keys", response_model=AgentKeyOut, status_code=201)
def create_agent_key(
    payload: AgentKeyCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Issue an endpoint-agent key. The raw key is returned exactly once."""
    target = db.query(User).filter(User.id == payload.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target user not found")
    row, raw_key = issue_agent_key(db, label=payload.label, user_id=payload.user_id, created_by=current_user.id)
    return AgentKeyOut(
        id=str(row.id),
        label=row.label,
        user_id=str(row.user_id),
        key=raw_key,
        created_at=row.created_at,
    )


@router.get("/agent-keys", response_model=list[AgentKeyListItem])
def list_agent_keys(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    keys = db.query(AgentKey).order_by(AgentKey.created_at.desc()).limit(200).all()
    return [
        AgentKeyListItem(
            id=str(k.id),
            label=k.label,
            user_id=str(k.user_id),
            active=k.active,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/agent-keys/{key_id}", status_code=204)
def revoke_agent_key(
    key_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    key = db.query(AgentKey).filter(AgentKey.id == key_id).first()
    if not key:
        raise HTTPException(status_code=404, detail="Agent key not found")
    key.active = False
    db.commit()
