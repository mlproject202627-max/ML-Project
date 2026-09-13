import math
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_security_analyst
from app.models.user import User
from app.models.activity import Activity
from app.schemas.activity import ActivityResponse, ActivityListResponse

router = APIRouter(prefix="/api/v1/activity", tags=["Activity"])


@router.get("", response_model=ActivityListResponse)
def list_activities(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    risk_level: Optional[str] = None,
    application: Optional[str] = None,
    sort_by: Optional[str] = "timestamp",
    sort_order: Optional[str] = "desc",
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    query = db.query(Activity)
    
    if user_id:
        query = query.filter(Activity.user_id == user_id)
    if event_type:
        query = query.filter(Activity.event_type == event_type)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.filter(Activity.timestamp >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.filter(Activity.timestamp <= dt_to)
        except ValueError:
            pass
    if application:
        query = query.filter(Activity.application == application)
    
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    sort_column = getattr(Activity, sort_by, Activity.timestamp)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    offset = (page - 1) * page_size
    activities = query.offset(offset).limit(page_size).all()
    
    return ActivityListResponse(
        items=[ActivityResponse(
            id=str(a.id),
            user_id=str(a.user_id),
            timestamp=a.timestamp,
            event_type=a.event_type,
            action=a.action,
            resource=a.resource,
            source_ip=a.source_ip,
            device=a.device,
            location=a.location,
            application=a.application,
            metadata=a.extra_metadata,
            risk_contribution=a.risk_contribution,
            created_at=a.created_at,
        ) for a in activities],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{user_id}/user", response_model=ActivityListResponse)
def get_user_activities(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    query = db.query(Activity).filter(Activity.user_id == user_id)
    
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    query = query.order_by(Activity.timestamp.desc())
    offset = (page - 1) * page_size
    activities = query.offset(offset).limit(page_size).all()
    
    return ActivityListResponse(
        items=[ActivityResponse(
            id=str(a.id),
            user_id=str(a.user_id),
            timestamp=a.timestamp,
            event_type=a.event_type,
            action=a.action,
            resource=a.resource,
            source_ip=a.source_ip,
            device=a.device,
            location=a.location,
            application=a.application,
            metadata=a.extra_metadata,
            risk_contribution=a.risk_contribution,
            created_at=a.created_at,
        ) for a in activities],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )
