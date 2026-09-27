"""API keys for endpoint agents (native daemons reporting OS-level telemetry).

Keys are created by an admin and shown once. Agents authenticate with
`X-Agent-Key: <key>`; the key maps to the user whose machine it monitors.
"""
import uuid
import secrets
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


def generate_agent_key() -> str:
    """sk_live_-prefixed random key; the raw value is only visible at creation."""
    return f"sk_live_{secrets.token_urlsafe(32)}"


class AgentKey(Base):
    __tablename__ = "agent_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    label = Column(String(255))                  # e.g. "Omar Haddad workstation"
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_agent_keys_user", "user_id"),
    )
