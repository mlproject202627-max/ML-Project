"""Schemas for the classified resource registry (spec §5)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResourceSummary(BaseModel):
    id: str
    resourceId: str
    name: str
    resourceType: str
    classification: str
    owner: Optional[str] = None
    ownerDepartment: Optional[str] = None
    customerId: Optional[str] = None
    fileName: Optional[str] = None
    fileSize: Optional[int] = None
    mime: Optional[str] = None
    downloadable: bool = True
    sensitive: bool = False
    createdAt: Optional[str] = None

    class Config:
        from_attributes = True


class ResourceDetail(ResourceSummary):
    """Adds the entitlement lists, so the UI can explain *why* something is
    restricted rather than only that it is."""

    allowedRoles: list[str] = []
    allowedDepartments: list[str] = []
    riskWeight: int = 0


class ResourceListResponse(BaseModel):
    items: list[ResourceSummary]
    total: int
    #: How many rows were hidden by entitlement. Non-zero is itself a signal
    #: worth showing: the portal is not pretending the material does not exist.
    withheld: int = 0


class ResourceAccessResponse(BaseModel):
    resource: ResourceSummary
    eventType: str
    recordedAt: datetime
    message: str
