"""Security telemetry: one row per meaningful employee action.

This is the spine of Sentinel. Every login, customer search, record view,
document download, sensitive access and simulated USB action lands here, and
everything downstream — baselines, rules, ML, risk, alerts — reads from it.

Design constraints:
- Structured columns over free-form JSON wherever the field is known and
  queried. `extra_metadata` carries only genuinely variable detail.
- No secrets, ever. Passwords, tokens and API keys have no representation here
  and must never be placed in `extra_metadata`.
- Append-only in practice: nothing in the application updates or deletes rows.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


#: Event vocabulary (spec §6). Kept as a module constant so the API layer,
#: rules engine and tests all validate against one list.
EVENT_TYPES = {
    # Authentication
    "LOGIN_SUCCESS", "LOGIN_FAILURE", "LOGOUT",
    # Customer / account activity
    "CUSTOMER_SEARCH", "CUSTOMER_VIEW", "ACCOUNT_VIEW",
    "TRANSACTION_VIEW", "LOAN_VIEW",
    # Documents and sensitive data
    "DOCUMENT_VIEW", "DOCUMENT_DOWNLOAD", "SENSITIVE_DATA_ACCESS",
    # Removable media (simulated)
    "USB_CONNECTED", "USB_DISCONNECTED", "FILE_TRANSFER_SIMULATED", "SENSITIVE_FILE_TRANSFER",
    # Contextual signals
    "AFTER_HOURS_ACCESS", "NEW_DEVICE_DETECTED", "LOCATION_ANOMALY",
    # Detection outcomes (written by the detection service)
    "THREAT_ALERT_CREATED",
    # Everything else a portal can do (tickets, preferences, exports). These
    # are recorded for completeness and baseline volume, not for threat rules.
    "INTERNAL_ACTION",
}

#: Severity assigned to an event before scoring (rules may escalate it).
EVENT_SEVERITY = {
    "LOGIN_FAILURE": "MEDIUM",
    "DOCUMENT_DOWNLOAD": "MEDIUM",
    "SENSITIVE_DATA_ACCESS": "HIGH",
    "SENSITIVE_FILE_TRANSFER": "CRITICAL",
    "FILE_TRANSFER_SIMULATED": "HIGH",
    "USB_CONNECTED": "MEDIUM",
    "USB_DISCONNECTED": "LOW",
    "AFTER_HOURS_ACCESS": "HIGH",
    "NEW_DEVICE_DETECTED": "MEDIUM",
    "LOCATION_ANOMALY": "HIGH",
    "THREAT_ALERT_CREATED": "CRITICAL",
}

SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

#: Sensitivity ladder recorded on the event (mirrors Resource classifications).
SENSITIVITIES = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "HIGHLY_CONFIDENTIAL", "RESTRICTED"]


class Activity(Base):
    """A single observed employee action."""

    __tablename__ = "activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(50), nullable=False)
    action = Column(String(255), nullable=False)

    # Human-readable target label ("customer:CUST-10021") kept for the timeline
    resource = Column(String(255))

    # -- structured references (spec §6) -----------------------------------
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)

    # -- request context ---------------------------------------------------
    source_ip = Column(String(45))
    device = Column(String(255))          # device label as reported
    location = Column(String(255))        # approximate location, e.g. "Vijayawada"
    country = Column(String(80))
    city = Column(String(80))
    application = Column(String(255))

    # -- assessment --------------------------------------------------------
    sensitivity = Column(String(24), default="INTERNAL")
    severity = Column(String(16), default="LOW")
    risk_contribution = Column(Float, default=0.0)

    extra_metadata = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="activities")
    anomalies = relationship("Anomaly", back_populates="activity")
    resource_ref = relationship("Resource", foreign_keys=[resource_id])
    device_ref = relationship("Device", foreign_keys=[device_id])
    customer_ref = relationship("Customer", foreign_keys=[customer_id])

    __table_args__ = (
        Index("idx_activities_user_id", "user_id"),
        Index("idx_activities_timestamp", "timestamp"),
        Index("idx_activities_event_type", "event_type"),
        Index("idx_activities_user_time", "user_id", "timestamp"),
        Index("idx_activities_severity", "severity"),
        Index("idx_activities_customer", "customer_id"),
        Index("idx_activities_resource", "resource_id"),
        Index("idx_activities_device", "device_id"),
    )

    def to_dict(self) -> dict:
        """Serialise for the API (employee timeline + admin activity views)."""
        return {
            "id": str(self.id),
            "employeeId": str(self.user_id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "eventType": self.event_type,
            "action": self.action,
            "resource": self.resource,
            "resourceId": str(self.resource_id) if self.resource_id else None,
            "customerId": str(self.customer_id) if self.customer_id else None,
            "deviceId": str(self.device_id) if self.device_id else None,
            "ipAddress": self.source_ip,
            "device": self.device,
            "location": self.location,
            "country": self.country,
            "city": self.city,
            "application": self.application,
            "sensitivity": self.sensitivity,
            "severity": self.severity,
            "riskContribution": self.risk_contribution or 0.0,
            "metadata": self.extra_metadata or {},
        }
