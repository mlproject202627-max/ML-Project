"""Discrete administrative operations performed on alerts.

Where `AuditLog` is the broad, immutable "everything that happened" trail,
`AdminAction` is the focused workflow record: one row per deliberate admin
operation on a threat alert, carrying the operator's note or the resolution
rationale.

The investigation notes an analyst types live here (action = ADD_NOTE), which
is why the alert detail view can reconstruct the full case history.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


#: Module-level action constants (imported by app.api.alerts and elsewhere)
VIEW_ALERT = "VIEW_ALERT"
START_INVESTIGATION = "START_INVESTIGATION"
ADD_NOTE = "ADD_NOTE"
RESOLVE_ALERT = "RESOLVE_ALERT"
MARK_FALSE_POSITIVE = "MARK_FALSE_POSITIVE"

#: Admin operations, mirroring the audit vocabulary in audit_log.py
ADMIN_ACTIONS = {
    "VIEW_ALERT",
    "START_INVESTIGATION",
    "ADD_NOTE",
    "RESOLVE_ALERT",
    "MARK_FALSE_POSITIVE",
    "ESCALATE",
    "REOPEN",
}


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    admin_code = Column(String(32))             # employee_code snapshot

    # Target alert. Nullable so the table can also record non-alert admin work.
    alert_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id"), nullable=True, index=True)

    action = Column(String(32), nullable=False, index=True)
    note = Column(Text)                         # investigation note / resolution reason / escalation reason

    # Alert status before and after, so the case timeline is reconstructable
    previous_status = Column(String(24))
    new_status = Column(String(24))

    details = Column(JSON, default=dict)

    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    admin = relationship("User", foreign_keys=[admin_id])
    alert = relationship("Anomaly", back_populates="admin_actions", foreign_keys=[alert_id])

    __table_args__ = (
        Index("idx_admin_actions_alert_time", "alert_id", "created_at"),
        Index("idx_admin_actions_admin", "admin_id"),
        Index("idx_admin_actions_action", "action"),
    )
