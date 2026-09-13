import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_security_analyst
from app.models.user import User, Role, user_roles
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.schemas.user import UserResponse, UserListResponse, RoleResponse

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )
    
    if department:
        query = query.filter(User.department == department)
    
    if status_filter:
        query = query.filter(User.status == status_filter)
    
    # Count
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Sorting
    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Pagination
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()
    
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse.model_validate(user)
