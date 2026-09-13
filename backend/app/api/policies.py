import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_admin, require_security_manager
from app.models.user import User
from app.models.detection_policy import DetectionPolicy
from app.schemas.policy import (
    PolicyResponse, PolicyListResponse,
    PolicyCreate, PolicyUpdate, PolicyStatusUpdate,
)

router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])


@router.get("", response_model=PolicyListResponse)
def list_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    detection_type: Optional[str] = None,
    enabled: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(DetectionPolicy)
    
    if detection_type:
        query = query.filter(DetectionPolicy.detection_type == detection_type)
    if enabled is not None:
        query = query.filter(DetectionPolicy.enabled == enabled)
    
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    query = query.order_by(DetectionPolicy.created_at.desc())
    offset = (page - 1) * page_size
    policies = query.offset(offset).limit(page_size).all()
    
    return PolicyListResponse(
        items=[PolicyResponse.model_validate(p) for p in policies],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(
    policy_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    policy = db.query(DetectionPolicy).filter(DetectionPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyResponse.model_validate(policy)


@router.post("", response_model=PolicyResponse, status_code=201)
def create_policy(
    data: PolicyCreate,
    current_user: User = Depends(require_security_manager),
    db: Session = Depends(get_db),
):
    policy = DetectionPolicy(
        name=data.name,
        description=data.description,
        detection_type=data.detection_type,
        enabled=data.enabled,
        severity=data.severity,
        threshold=data.threshold,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.put("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: str,
    update_data: PolicyUpdate,
    current_user: User = Depends(require_security_manager),
    db: Session = Depends(get_db),
):
    policy = db.query(DetectionPolicy).filter(DetectionPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(policy, key, value)
    policy.updated_by = current_user.id
    
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=204)
def delete_policy(
    policy_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    policy = db.query(DetectionPolicy).filter(DetectionPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    return None


@router.patch("/{policy_id}/status", response_model=PolicyResponse)
def toggle_policy_status(
    policy_id: str,
    data: PolicyStatusUpdate,
    current_user: User = Depends(require_security_manager),
    db: Session = Depends(get_db),
):
    policy = db.query(DetectionPolicy).filter(DetectionPolicy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    policy.enabled = data.enabled
    policy.updated_by = current_user.id
    
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)
