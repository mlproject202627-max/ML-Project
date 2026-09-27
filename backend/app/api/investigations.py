import math
import uuid as uuid_mod
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_security_analyst, require_security_manager
from app.models.user import User
from app.models.investigation import Investigation, InvestigationEvent
from app.schemas.investigation import (
    InvestigationResponse, InvestigationListResponse,
    InvestigationCreate, InvestigationUpdate, InvestigationAssign,
    InvestigationEventResponse,
)

router = APIRouter(prefix="/api/v1/investigations", tags=["Investigations"])


@router.get("", response_model=InvestigationListResponse)
def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    query = db.query(Investigation)
    
    if status_filter:
        query = query.filter(Investigation.status == status_filter)
    if priority:
        query = query.filter(Investigation.priority == priority)
    if assigned_to:
        query = query.filter(Investigation.assigned_to == assigned_to)
    
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    sort_column = getattr(Investigation, sort_by, Investigation.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    offset = (page - 1) * page_size
    investigations = query.offset(offset).limit(page_size).all()
    
    items = []
    for inv in investigations:
        events = db.query(InvestigationEvent).filter(
            InvestigationEvent.investigation_id == inv.id
        ).order_by(InvestigationEvent.created_at).all()
        
        items.append(InvestigationResponse(
            id=str(inv.id),
            anomaly_id=str(inv.anomaly_id),
            assigned_to=str(inv.assigned_to) if inv.assigned_to else None,
            title=inv.title,
            summary=inv.summary,
            status=inv.status,
            priority=inv.priority,
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            resolved_at=inv.resolved_at,
            events=[InvestigationEventResponse(
                id=str(e.id),
                investigation_id=str(e.investigation_id),
                actor_id=str(e.actor_id) if e.actor_id else None,
                action=e.action,
                description=e.description,
                created_at=e.created_at,
            ) for e in events],
        ))
    
    return InvestigationListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(
    investigation_id: str,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    # Coerce to UUID: Postgres accepts strings, SQLite (tests) requires UUID objects
    try:
        _iid = uuid_mod.UUID(str(investigation_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv = db.query(Investigation).filter(Investigation.id == _iid).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    events = db.query(InvestigationEvent).filter(
        InvestigationEvent.investigation_id == inv.id
    ).order_by(InvestigationEvent.created_at).all()
    
    return InvestigationResponse(
        id=str(inv.id),
        anomaly_id=str(inv.anomaly_id),
        assigned_to=str(inv.assigned_to) if inv.assigned_to else None,
        title=inv.title,
        summary=inv.summary,
        status=inv.status,
        priority=inv.priority,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        resolved_at=inv.resolved_at,
        events=[InvestigationEventResponse(
            id=str(e.id),
            investigation_id=str(e.investigation_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            description=e.description,
            created_at=e.created_at,
        ) for e in events],
    )


@router.post("", response_model=InvestigationResponse, status_code=201)
def create_investigation(
    data: InvestigationCreate,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    inv = Investigation(
        # Coerce to UUID: Postgres accepts strings, SQLite (tests) requires UUID objects
        anomaly_id=uuid_mod.UUID(str(data.anomaly_id)),
        title=data.title,
        summary=data.summary,
        priority=data.priority,
        status="OPEN",
    )
    db.add(inv)
    db.flush()
    
    event = InvestigationEvent(
        investigation_id=inv.id,
        actor_id=current_user.id,
        action="CREATED",
        description=f"Investigation created by {current_user.name}",
    )
    db.add(event)
    db.commit()
    db.refresh(inv)
    
    return InvestigationResponse(
        id=str(inv.id),
        anomaly_id=str(inv.anomaly_id),
        assigned_to=None,
        title=inv.title,
        summary=inv.summary,
        status=inv.status,
        priority=inv.priority,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        resolved_at=None,
        events=[InvestigationEventResponse(
            id=str(event.id),
            investigation_id=str(event.investigation_id),
            actor_id=str(event.actor_id),
            action=event.action,
            description=event.description,
            created_at=event.created_at,
        )],
    )


@router.patch("/{investigation_id}", response_model=InvestigationResponse)
def update_investigation(
    investigation_id: str,
    update_data: InvestigationUpdate,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    # Coerce to UUID: Postgres accepts strings, SQLite (tests) requires UUID objects
    try:
        _iid = uuid_mod.UUID(str(investigation_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv = db.query(Investigation).filter(Investigation.id == _iid).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(inv, key, value)
    
    event = InvestigationEvent(
        investigation_id=inv.id,
        actor_id=current_user.id,
        action="UPDATED",
        description=f"Investigation updated by {current_user.name}",
    )
    db.add(event)
    db.commit()
    db.refresh(inv)
    
    events = db.query(InvestigationEvent).filter(
        InvestigationEvent.investigation_id == inv.id
    ).order_by(InvestigationEvent.created_at).all()
    
    return InvestigationResponse(
        id=str(inv.id),
        anomaly_id=str(inv.anomaly_id),
        assigned_to=str(inv.assigned_to) if inv.assigned_to else None,
        title=inv.title,
        summary=inv.summary,
        status=inv.status,
        priority=inv.priority,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        resolved_at=inv.resolved_at,
        events=[InvestigationEventResponse(
            id=str(e.id),
            investigation_id=str(e.investigation_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            description=e.description,
            created_at=e.created_at,
        ) for e in events],
    )


@router.post("/{investigation_id}/assign", response_model=InvestigationResponse)
def assign_investigation(
    investigation_id: str,
    data: InvestigationAssign,
    current_user: User = Depends(require_security_manager),
    db: Session = Depends(get_db),
):
    # Coerce to UUID: Postgres accepts strings, SQLite (tests) requires UUID objects
    try:
        _iid = uuid_mod.UUID(str(investigation_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv = db.query(Investigation).filter(Investigation.id == _iid).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    inv.assigned_to = data.assigned_to
    inv.status = "ASSIGNED"
    
    assigned_user = db.query(User).filter(User.id == data.assigned_to).first()
    event = InvestigationEvent(
        investigation_id=inv.id,
        actor_id=current_user.id,
        action="ASSIGNED",
        description=f"Investigation assigned to {assigned_user.name if assigned_user else data.assigned_to} by {current_user.name}",
    )
    db.add(event)
    db.commit()
    db.refresh(inv)
    
    events = db.query(InvestigationEvent).filter(
        InvestigationEvent.investigation_id == inv.id
    ).order_by(InvestigationEvent.created_at).all()
    
    return InvestigationResponse(
        id=str(inv.id),
        anomaly_id=str(inv.anomaly_id),
        assigned_to=str(inv.assigned_to) if inv.assigned_to else None,
        title=inv.title,
        summary=inv.summary,
        status=inv.status,
        priority=inv.priority,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        resolved_at=inv.resolved_at,
        events=[InvestigationEventResponse(
            id=str(e.id),
            investigation_id=str(e.investigation_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            description=e.description,
            created_at=e.created_at,
        ) for e in events],
    )


@router.post("/{investigation_id}/resolve", response_model=InvestigationResponse)
def resolve_investigation(
    investigation_id: str,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    # Coerce to UUID: Postgres accepts strings, SQLite (tests) requires UUID objects
    try:
        _iid = uuid_mod.UUID(str(investigation_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Investigation not found")
    inv = db.query(Investigation).filter(Investigation.id == _iid).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    inv.status = "RESOLVED"
    inv.resolved_at = datetime.now(timezone.utc)
    
    event = InvestigationEvent(
        investigation_id=inv.id,
        actor_id=current_user.id,
        action="RESOLVED",
        description=f"Investigation resolved by {current_user.name}",
    )
    db.add(event)
    db.commit()
    db.refresh(inv)
    
    events = db.query(InvestigationEvent).filter(
        InvestigationEvent.investigation_id == inv.id
    ).order_by(InvestigationEvent.created_at).all()
    
    return InvestigationResponse(
        id=str(inv.id),
        anomaly_id=str(inv.anomaly_id),
        assigned_to=str(inv.assigned_to) if inv.assigned_to else None,
        title=inv.title,
        summary=inv.summary,
        status=inv.status,
        priority=inv.priority,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        resolved_at=inv.resolved_at,
        events=[InvestigationEventResponse(
            id=str(e.id),
            investigation_id=str(e.investigation_id),
            actor_id=str(e.actor_id) if e.actor_id else None,
            action=e.action,
            description=e.description,
            created_at=e.created_at,
        ) for e in events],
    )
