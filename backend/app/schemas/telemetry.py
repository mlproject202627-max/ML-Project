"""Request/response schemas for real-time telemetry."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

VALID_EVENT_TYPES = {
    "LOGIN_TIME", "LOGOUT_TIME", "LOCATION_UPDATE", "USB_ATTACH", "USB_ACCESS",
    "FILE_UPLOAD", "FILE_DROP", "DATA_ACCESS", "VIEW_DWELL", "HEARTBEAT",
}


class TelemetryEventIn(BaseModel):
    """One observed moment from the browser client or the endpoint agent."""
    event_type: str = Field(..., description="One of " + ", ".join(sorted(VALID_EVENT_TYPES)))
    occurred_at: datetime
    source: str = "browser"
    ip_address: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    accuracy_m: Optional[float] = None
    device: Optional[str] = None
    resource: Optional[str] = None
    application: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    risk_contribution: float = 0.0


class TelemetryBatchIn(BaseModel):
    """Batch of telemetry moments (browser flushes on an interval)."""
    events: List[TelemetryEventIn] = Field(..., max_length=200)


class TelemetryEventOut(BaseModel):
    id: str
    user_id: str
    event_type: str
    source: str
    occurred_at: datetime
    received_at: datetime
    ip_address: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    accuracy_m: Optional[float] = None
    device: Optional[str] = None
    resource: Optional[str] = None
    application: Optional[str] = None
    metadata: Dict[str, Any] = {}
    risk_contribution: float = 0.0


class TelemetryIngestResult(BaseModel):
    received: int
    stored: int
    rejected: int
    errors: List[str] = []


class AgentKeyCreate(BaseModel):
    label: str
    user_id: str


class AgentKeyOut(BaseModel):
    id: str
    label: Optional[str] = None
    user_id: str
    key: str  # raw key — shown exactly once at creation
    created_at: datetime


class AgentKeyListItem(BaseModel):
    id: str
    label: Optional[str] = None
    user_id: str
    active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
