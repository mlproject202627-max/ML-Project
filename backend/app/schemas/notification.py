from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    message: Optional[str] = None
    related_anomaly_id: Optional[str] = None
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
