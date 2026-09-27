"""Schemas for the simulated USB / removable-media workflow (spec §10)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UsbConnectRequest(BaseModel):
    deviceLabel: str = Field(
        ...,
        min_length=3,
        max_length=80,
        description="Stable label for the simulated device, e.g. USB-DEMO-1024",
    )


class UsbTransferRequest(BaseModel):
    deviceLabel: str = Field(..., min_length=3, max_length=80)
    #: Transfer a registered resource (preferred — carries its classification),
    #: or a free-form file when demonstrating an unregistered one.
    resourceId: Optional[str] = None
    fileName: Optional[str] = Field(None, max_length=255)
    fileSize: Optional[int] = Field(None, ge=0)
    classification: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)


class UsbEventOut(BaseModel):
    id: str
    deviceLabel: str
    action: str
    fileName: Optional[str] = None
    fileSize: Optional[int] = None
    classification: Optional[str] = None
    resourceId: Optional[str] = None
    occurredAt: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class UsbActionResponse(BaseModel):
    event: UsbEventOut
    message: str
    #: True when the action was serious enough to be treated as a security
    #: event rather than routine device activity.
    flagged: bool = False
