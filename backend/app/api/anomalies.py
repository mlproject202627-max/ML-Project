import math
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_security_analyst
from app.models.user import User
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.schemas.anomaly import AnomalyResponse, AnomalyListResponse, AnomalyUpdate, RiskFactorResponse

router = APIRouter(prefix="/api/v1/anomalies", tags=["Anomalies"])


@router.get("", response_model=AnomalyListResponse)
def list_anomalies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    severity: Optional[str] = None,
    status_filter: Optional[str] = None,
    detection_type: Optional[str] = None,
    user_id: Optional[str] = None,
    minimum_risk_score: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: Optional[str] = "detected_at",
    sort_order: Optional[str] = "desc",
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    query = db.query(Anomaly)
    
    if severity:
        query = query.filter(Anomaly.severity == severity)
    if status_filter:
        query = query.filter(Anomaly.status == status_filter)
    if detection_type:
        query = query.filter(Anomaly.detection_type == detection_type)
    if user_id:
        query = query.filter(Anomaly.user_id == user_id)
    if minimum_risk_score is not None:
        query = query.filter(Anomaly.risk_score >= minimum_risk_score)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.filter(Anomaly.detected_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.filter(Anomaly.detected_at <= dt_to)
        except ValueError:
            pass
    
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    sort_column = getattr(Anomaly, sort_by, Anomaly.detected_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    offset = (page - 1) * page_size
    anomalies = query.offset(offset).limit(page_size).all()
    
    # Eager load risk factors
    items = []
    for anomaly in anomalies:
        risk_factors = db.query(RiskEvent).filter(RiskEvent.anomaly_id == anomaly.id).all()
        items.append(AnomalyResponse(
            id=str(anomaly.id),
            user_id=str(anomaly.user_id),
            activity_id=str(anomaly.activity_id) if anomaly.activity_id else None,
            detection_type=anomaly.detection_type,
            severity=anomaly.severity,
            risk_score=anomaly.risk_score,
            anomaly_score=anomaly.anomaly_score,
            confidence=anomaly.confidence,
            description=anomaly.description,
            status=anomaly.status,
            detected_at=anomaly.detected_at,
            created_at=anomaly.created_at,
            updated_at=anomaly.updated_at,
            risk_factors=[RiskFactorResponse(
                id=str(rf.id),
                signal_type=rf.signal_type,
                signal_value=rf.signal_value,
                weight=rf.weight,
                contribution=rf.contribution,
            ) for rf in risk_factors],
        ))
    
    return AnomalyListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{anomaly_id}", response_model=AnomalyResponse)
def get_anomaly(
    anomaly_id: str,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    risk_factors = db.query(RiskEvent).filter(RiskEvent.anomaly_id == anomaly.id).all()
    
    return AnomalyResponse(
        id=str(anomaly.id),
        user_id=str(anomaly.user_id),
        activity_id=str(anomaly.activity_id) if anomaly.activity_id else None,
        detection_type=anomaly.detection_type,
        severity=anomaly.severity,
        risk_score=anomaly.risk_score,
        anomaly_score=anomaly.anomaly_score,
        confidence=anomaly.confidence,
        description=anomaly.description,
        status=anomaly.status,
        detected_at=anomaly.detected_at,
        created_at=anomaly.created_at,
        updated_at=anomaly.updated_at,
        risk_factors=[RiskFactorResponse(
            id=str(rf.id),
            signal_type=rf.signal_type,
            signal_value=rf.signal_value,
            weight=rf.weight,
            contribution=rf.contribution,
        ) for rf in risk_factors],
    )


@router.patch("/{anomaly_id}", response_model=AnomalyResponse)
def update_anomaly(
    anomaly_id: str,
    update_data: AnomalyUpdate,
    current_user: User = Depends(require_security_analyst),
    db: Session = Depends(get_db),
):
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(anomaly, key, value)
    
    db.commit()
    db.refresh(anomaly)
    
    risk_factors = db.query(RiskEvent).filter(RiskEvent.anomaly_id == anomaly.id).all()
    
    return AnomalyResponse(
        id=str(anomaly.id),
        user_id=str(anomaly.user_id),
        activity_id=str(anomaly.activity_id) if anomaly.activity_id else None,
        detection_type=anomaly.detection_type,
        severity=anomaly.severity,
        risk_score=anomaly.risk_score,
        anomaly_score=anomaly.anomaly_score,
        confidence=anomaly.confidence,
        description=anomaly.description,
        status=anomaly.status,
        detected_at=anomaly.detected_at,
        created_at=anomaly.created_at,
        updated_at=anomaly.updated_at,
        risk_factors=[RiskFactorResponse(
            id=str(rf.id),
            signal_type=rf.signal_type,
            signal_value=rf.signal_value,
            weight=rf.weight,
            contribution=rf.contribution,
        ) for rf in risk_factors],
    )
