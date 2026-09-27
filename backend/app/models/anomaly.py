"""ThreatAlert — the security alert raised when an employee's behaviour crosses
a risk threshold.

This table was originally `Anomaly` (a generic UEBA detection row). It has been
extended in place to carry the full alert lifecycle the admin portal needs:
who triggered it, why, what the score was, and how it was resolved.

Lifecycle:
    OPEN ──► INVESTIGATING ──► RESOLVED
      └────────────────────────► FALSE_POSITIVE

An alert is never deleted. Resolution annotates the row; the audit trail in
`audit_logs` and `admin_actions` records every transition.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


#: Alert status vocabulary (spec §17).
ALERT_STATUSES = {"OPEN", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"}

#: Statuses that still require analyst attention.
ACTIVE_ALERT_STATUSES = ["OPEN", "INVESTIGATING"]

#: Legacy statuses kept readable so pre-existing seeded rows still render.
LEGACY_STATUS_ALIASES = {
    "NEW": "OPEN",
    "IN_REVIEW": "INVESTIGATING",
    "ASSIGNED": "INVESTIGATING",
    "ESCALATED": "INVESTIGATING",
    "CONTAINED": "RESOLVED",
    "DISMISSED": "FALSE_POSITIVE",
}

ALERT_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class Anomaly(Base):
    """A raised threat alert. Table name stays `anomalies` for compatibility."""

    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activities.id"), nullable=True)

    # -- classification ----------------------------------------------------
    detection_type = Column(String(50), nullable=False)   # rule family, e.g. RULE-007 or ISOLATION_FOREST
    severity = Column(String(20), nullable=False)
    title = Column(String(255))                           # short headline for the queue
    description = Column(String(1000))                    # human-readable narrative

    # -- scoring -----------------------------------------------------------
    risk_score = Column(Float, nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False)         # normalised 0–1
    confidence = Column(Float, nullable=False)
    ml_anomaly_score = Column(Float, nullable=True)       # raw Isolation Forest output
    baseline_deviation = Column(Float, nullable=True)     # sigmas from the employee's own baseline

    # -- explainability ----------------------------------------------------
    # {"rules": [{"code": "RULE-004", "label": "...", "contribution": 12.0}], "features": {...}}
    trigger = Column(String(500))                         # what fired, in one line
    rule_hits = Column(JSON, default=list)                # every rule that contributed
    evidence = Column(JSON, default=dict)                 # supporting facts for the analyst

    # -- lifecycle ---------------------------------------------------------
    status = Column(String(20), nullable=False, default="OPEN")
    detected_at = Column(DateTime(timezone=True), nullable=False)
    resolved_at = Column(DateTime(timezone=True))
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_reason = Column(Text)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="anomalies", foreign_keys=[user_id])
    activity = relationship("Activity", back_populates="anomalies")
    resolver = relationship("User", foreign_keys=[resolved_by])
    risk_events = relationship("RiskEvent", back_populates="anomaly")
    investigations = relationship("Investigation", back_populates="anomaly")
    notification = relationship("Notification", back_populates="anomaly", uselist=False)
    admin_actions = relationship("AdminAction", back_populates="alert", foreign_keys="AdminAction.alert_id")

    __table_args__ = (
        Index("idx_anomalies_user_id", "user_id"),
        Index("idx_anomalies_severity", "severity"),
        Index("idx_anomalies_status", "status"),
        Index("idx_anomalies_detected_at", "detected_at"),
        Index("idx_anomalies_risk_score", "risk_score"),
        Index("idx_anomalies_user_status", "user_id", "status"),
    )

    @property
    def normalised_status(self) -> str:
        """Map any legacy status onto the current vocabulary."""
        if self.status in ALERT_STATUSES:
            return self.status
        return LEGACY_STATUS_ALIASES.get(self.status or "", "OPEN")

    @property
    def is_active(self) -> bool:
        return self.normalised_status in ACTIVE_ALERT_STATUSES

    def to_dict(self) -> dict:
        """Serialise for the alert queue and detail views."""
        return {
            "id": str(self.id),
            "employeeId": str(self.user_id),
            "employeeName": self.user.name if self.user else None,
            "employeeCode": self.user.employee_code if self.user else None,
            "department": self.user.department if self.user else None,
            "detectionType": self.detection_type,
            "severity": self.severity,
            "title": self.title or (self.description or "")[:120],
            "description": self.description,
            "trigger": self.trigger,
            "riskScore": self.risk_score,
            "anomalyScore": self.anomaly_score,
            "mlAnomalyScore": self.ml_anomaly_score,
            "baselineDeviation": self.baseline_deviation,
            "confidence": self.confidence,
            "ruleHits": self.rule_hits or [],
            "evidence": self.evidence or {},
            "status": self.normalised_status,
            "detectedAt": self.detected_at.isoformat() if self.detected_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolvedBy": str(self.resolved_by) if self.resolved_by else None,
            "resolutionReason": self.resolution_reason,
        }
