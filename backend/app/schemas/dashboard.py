from pydantic import BaseModel
from typing import List, Optional


class DashboardMetrics(BaseModel):
    openAlerts: int
    identitiesWatched: int
    anomaliesDetected: int
    meanRiskIndex: float
    watchlistCount: int


class TrendPoint(BaseModel):
    label: str
    anomalies: int
    meanRisk: float
    baseline: float


class DetectionMixItem(BaseModel):
    kind: str
    count: int


class TriageItem(BaseModel):
    id: str
    headline: str
    severity: str
    risk_score: float
    status: str
    employee_id: str


class DriftItem(BaseModel):
    id: str
    name: str
    drift: float
    department: str
    risk_score: float


class DashboardResponse(BaseModel):
    metrics: DashboardMetrics
    anomalyTrend: List[TrendPoint]
    detectionMix: List[DetectionMixItem]
    priorityTriage: List[TriageItem]
    behaviourDrift: List[DriftItem]
