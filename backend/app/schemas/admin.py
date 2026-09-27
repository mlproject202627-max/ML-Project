"""Schemas for the security operations console (spec §14–§19)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------

class EmployeeRiskSummary(BaseModel):
    """One row in the monitored-employee list."""

    id: str
    name: str
    email: str
    employeeCode: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    jobTitle: Optional[str] = None
    branchName: Optional[str] = None
    status: str = "ACTIVE"

    riskScore: float = 0.0
    riskLevel: str = "LOW"
    riskChange: float = 0.0

    openAlerts: int = 0
    lastActivityAt: Optional[datetime] = None
    lastLoginAt: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    items: list[EmployeeRiskSummary]
    total: int
    page: int
    pageSize: int


# ---------------------------------------------------------------------------
# Alerts / investigation workflow (spec §17, §19)
# ---------------------------------------------------------------------------

class AlertNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)


class AlertResolveRequest(BaseModel):
    """Resolution requires a reason — an unexplained closure is not an audit
    record an investigator can defend six months later."""

    resolutionReason: str = Field(..., min_length=3, max_length=2000)
    outcome: str = Field(
        "RESOLVED",
        description="RESOLVED or FALSE_POSITIVE",
    )


class AlertSummary(BaseModel):
    id: str
    employeeId: str
    employeeName: Optional[str] = None
    employeeCode: Optional[str] = None
    department: Optional[str] = None
    severity: str
    title: str
    description: Optional[str] = None
    trigger: Optional[str] = None
    riskScore: float
    status: str
    detectedAt: Optional[datetime] = None
    resolvedAt: Optional[datetime] = None
    createdAt: Optional[datetime] = None

    # `detectionType` is the rule family (`RULE-007`, `ISOLATION_FOREST`, …).
    # The queue groups and colour-codes by it, so without it every row would
    # have to be classified from its free-text title. `confidence` is shown as
    # a meter on the queue row. Both are already columns on the model; they
    # were simply absent from this projection.
    detectionType: Optional[str] = None
    confidence: float = 0.0

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    items: list[AlertSummary]
    total: int
    page: int
    pageSize: int
    counts: dict[str, int] = {}


class AlertDetailResponse(BaseModel):
    """Everything the investigation view needs, in one response.

    Assembled server-side deliberately: the alternative is the frontend making
    eight round trips and rendering a half-populated case while an analyst is
    trying to make a judgement call.
    """

    alert: dict[str, Any]
    employee: dict[str, Any]
    baseline: Optional[dict[str, Any]] = None
    riskHistory: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Audit log (spec §18)
# ---------------------------------------------------------------------------

class AuditLogEntry(BaseModel):
    id: str
    actorId: Optional[str] = None
    actorCode: Optional[str] = None
    actorType: str
    action: str
    targetType: Optional[str] = None
    targetId: Optional[str] = None
    description: Optional[str] = None
    ipAddress: Optional[str] = None
    requestId: Optional[str] = None
    details: dict[str, Any] = {}
    createdAt: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    pageSize: int


# ---------------------------------------------------------------------------
# Timeline (spec §16)
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    id: str
    timestamp: Optional[datetime] = None
    eventType: str
    action: str
    employeeId: str
    employeeName: Optional[str] = None
    employeeCode: Optional[str] = None
    resource: Optional[str] = None
    sensitivity: Optional[str] = None
    severity: Optional[str] = None
    riskContribution: float = 0.0
    location: Optional[str] = None
    device: Optional[str] = None
    ipAddress: Optional[str] = None
    metadata: dict[str, Any] = {}

    class Config:
        from_attributes = True


class TimelineResponse(BaseModel):
    items: list[TimelineEvent]
    total: int
    page: int
    pageSize: int
