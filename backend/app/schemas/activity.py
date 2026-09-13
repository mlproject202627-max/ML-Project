from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class ActivityResponse(BaseModel):
    id: str
    user_id: str
    timestamp: datetime
    event_type: str
    action: str
    resource: Optional[str] = None
    source_ip: Optional[str] = None
    device: Optional[str] = None
    location: Optional[str] = None
    application: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    risk_contribution: float = 0.0
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    items: List[ActivityResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class ActivityIngestRequest(BaseModel):
    user_id: str
    timestamp: str
    event_type: str
    action: str
    resource: Optional[str] = None
    source_ip: Optional[str] = None
    device: Optional[str] = None
    location: Optional[str] = None
    application: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
