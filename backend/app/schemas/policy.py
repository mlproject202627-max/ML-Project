from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    detection_type: str
    enabled: bool
    severity: str
    threshold: float
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PolicyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    detection_type: str
    enabled: bool = True
    severity: str = "MEDIUM"
    threshold: float = 0.7


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    severity: Optional[str] = None
    threshold: Optional[float] = None


class PolicyStatusUpdate(BaseModel):
    enabled: bool


class PolicyListResponse(BaseModel):
    items: List[PolicyResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
