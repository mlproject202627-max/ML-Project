from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.schemas.dashboard import (
    DashboardResponse, DashboardMetrics, TrendPoint,
    DetectionMixItem, TriageItem, DriftItem
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Core metrics
    open_alerts = db.query(func.count(Anomaly.id)).filter(
        Anomaly.status.in_(["OPEN", "IN_REVIEW", "ESCALATED"])
    ).scalar() or 0
    
    identities_watched = db.query(func.count(User.id)).filter(
        User.status == "ACTIVE"
    ).scalar() or 0
    
    anomalies_detected = db.query(func.count(Anomaly.id)).scalar() or 0
    
    mean_risk = db.query(func.avg(Anomaly.risk_score)).scalar() or 0.0
    
    watchlist_count = db.query(func.count(User.id)).filter(
        User.status == "ACTIVE"
    ).scalar() or 0
    
    # Anomaly trend (last 14 days)
    anomaly_trend = []
    for i in range(14):
        date = datetime.now(timezone.utc) - timedelta(days=13 - i)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        count = db.query(func.count(Anomaly.id)).filter(
            Anomaly.detected_at >= date_start,
            Anomaly.detected_at < date_end
        ).scalar() or 0
        
        avg_risk = db.query(func.avg(Anomaly.risk_score)).filter(
            Anomaly.detected_at >= date_start,
            Anomaly.detected_at < date_end
        ).scalar() or 0.0
        
        anomaly_trend.append(TrendPoint(
            label=date_start.strftime("%b %d"),
            anomalies=count,
            meanRisk=round(avg_risk, 1),
            baseline=12.0,
        ))
    
    # Detection mix
    detection_mix_rows = db.query(
        Anomaly.detection_type,
        func.count(Anomaly.id)
    ).group_by(Anomaly.detection_type).all()
    
    detection_mix = [
        DetectionMixItem(kind=row[0], count=row[1])
        for row in detection_mix_rows
    ]
    
    # Priority triage (top 10 open anomalies by risk)
    triage_rows = db.query(Anomaly).filter(
        Anomaly.status.in_(["OPEN", "IN_REVIEW", "ESCALATED"])
    ).order_by(Anomaly.risk_score.desc()).limit(10).all()
    
    priority_triage = [
        TriageItem(
            id=str(a.id),
            headline=a.description or f"{a.detection_type} detected",
            severity=a.severity,
            risk_score=a.risk_score,
            status=a.status,
            employee_id=str(a.user_id),
        )
        for a in triage_rows
    ]
    
    # Behaviour drift (top 10 users by drift)
    drift_rows = db.query(
        User.id,
        User.name,
        User.department,
        func.max(RiskEvent.signal_value).label("max_drift"),
    ).join(RiskEvent, RiskEvent.user_id == User.id).group_by(
        User.id, User.name, User.department
    ).order_by(func.max(RiskEvent.signal_value).desc()).limit(10).all()
    
    behaviour_drift = [
        DriftItem(
            id=str(row[0]),
            name=row[1],
            drift=round(row[3] or 0, 1),
            department=row[2] or "Unknown",
            risk_score=0.0,
        )
        for row in drift_rows
    ]
    
    return DashboardResponse(
        metrics=DashboardMetrics(
            openAlerts=open_alerts,
            identitiesWatched=identities_watched,
            anomaliesDetected=anomalies_detected,
            meanRiskIndex=round(float(mean_risk), 1),
            watchlistCount=watchlist_count,
        ),
        anomalyTrend=anomaly_trend,
        detectionMix=detection_mix,
        priorityTriage=priority_triage,
        behaviourDrift=behaviour_drift,
    )
