from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class InvestigationEventResponse(BaseModel):
    id: str
    investigation_id: str
    actor_id: Optional[str] = None
    action: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InvestigationResponse(BaseModel):
    id: str
    anomaly_id: str
    assigned_to: Optional[str] = None
    title: str
    summary: Optional[str] = None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    events: List[InvestigationEventResponse] = []

    class Config:
        from_attributes = True


class InvestigationCreate(BaseModel):
    anomaly_id: str
    title: str
    summary: Optional[str] = None
    priority: str = "MEDIUM"


class InvestigationUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class InvestigationAssign(BaseModel):
    assigned_to: str


class InvestigationListResponse(BaseModel):
    items: List[InvestigationResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
