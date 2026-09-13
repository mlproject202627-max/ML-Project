from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class RiskFactorResponse(BaseModel):
    id: str
    signal_type: str
    signal_value: float
    weight: float
    contribution: float

    class Config:
        from_attributes = True


class AnomalyResponse(BaseModel):
    id: str
    user_id: str
    activity_id: Optional[str] = None
    detection_type: str
    severity: str
    risk_score: float
    anomaly_score: float
    confidence: float
    description: Optional[str] = None
    status: str
    detected_at: datetime
    created_at: datetime
    updated_at: datetime
    risk_factors: List[RiskFactorResponse] = []

    class Config:
        from_attributes = True


class AnomalyUpdate(BaseModel):
    status: Optional[str] = None
    severity: Optional[str] = None
    assigned_to: Optional[str] = None


class AnomalyListResponse(BaseModel):
    items: List[AnomalyResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
