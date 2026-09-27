"""Append-only audit log.

Every security-relevant action — employee activity, admin operations,
authentication events, alert lifecycle changes — is recorded here.

Immutability contract:
- No ORM relationships are declared back into this table, and nothing in the
  application ever issues UPDATE or DELETE against it. `AuditLog` has no
  `updated_at` column precisely so that "was this edited?" is unanswerable.
- The API exposes read-only endpoints. There is deliberately no write route.

Nothing secret is ever written: no passwords, tokens, secrets or API keys.
Callers pass business identifiers (alert id, employee code), never credentials.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


# -- action vocabulary -------------------------------------------------------

# Authentication
AUTH_LOGIN_SUCCESS = "LOGIN_SUCCESS"
AUTH_LOGIN_FAILURE = "LOGIN_FAILURE"
AUTH_LOGOUT = "LOGOUT"

# Employee activity (mirrored for the audit trail; full detail lives in activities)
EMPLOYEE_ACTION = "EMPLOYEE_ACTION"
SENSITIVE_ACCESS = "SENSITIVE_ACCESS"
DOCUMENT_DOWNLOAD = "DOCUMENT_DOWNLOAD"
USB_EVENT = "USB_EVENT"

# Alert lifecycle
VIEW_ALERT = "VIEW_ALERT"
START_INVESTIGATION = "START_INVESTIGATION"
ADD_NOTE = "ADD_NOTE"
RESOLVE_ALERT = "RESOLVE_ALERT"
MARK_FALSE_POSITIVE = "MARK_FALSE_POSITIVE"

# Risk/detection
RISK_CHANGE = "RISK_CHANGE"
ALERT_CREATED = "ALERT_CREATED"
# An operator clearing an employee's carried risk. Appends a zero-score row; it
# never deletes the scores, alerts or events that came before.
RESET_RISK = "RESET_RISK"

# Administration
USER_CREATED = "USER_CREATED"
USER_UPDATED = "USER_UPDATED"
ROLE_CHANGED = "ROLE_CHANGED"
# Demo mode injects synthetic security events under a real employee's identity.
# That is indistinguishable from a genuine incident unless it is labelled, so
# every scenario run appends this action with the operator who triggered it.
DEMO_SCENARIO_RUN = "DEMO_SCENARIO_RUN"
DEMO_HISTORY_GENERATED = "DEMO_HISTORY_GENERATED"

ACTOR_TYPES = {"EMPLOYEE", "ADMIN", "SYSTEM"}


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who acted. Null actor_id + actor_type=SYSTEM covers automated detections.
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    actor_code = Column(String(32))            # employee_code snapshot (survives renames)
    actor_type = Column(String(16), nullable=False, default="EMPLOYEE")

    action = Column(String(40), nullable=False, index=True)
    target_type = Column(String(40))           # ALERT / EMPLOYEE / RESOURCE / DOCUMENT / SESSION / USB
    target_id = Column(String(64), index=True)  # id or business key of the target
    description = Column(Text)

    # Request provenance
    ip_address = Column(String(45))
    request_id = Column(String(64), index=True)
    user_agent = Column(String(256))

    # Small structured payload — never credentials or tokens
    details = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    actor = relationship("User", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_audit_logs_actor_time", "actor_id", "created_at"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_target", "target_type", "target_id"),
    )
