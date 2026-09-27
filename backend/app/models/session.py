"""Login session tracking for real users.

A UserSession row is created on every successful login and closed on logout,
giving the platform ground truth about who logged in, from where, when, and
on what device.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)

    # "where" and "what device" at login time
    ip_address = Column(String(45))
    user_agent = Column(String(512))
    location = Column(String(255))  # e.g. "Bengaluru, IN" resolved by the browser
    latitude = Column(String(32))   # stored as string to avoid float issues; "denied" allowed
    longitude = Column(String(32))

    # Lifecycle
    logged_in_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    logged_out_at = Column(DateTime(timezone=True))
    active = Column(Boolean, nullable=False, default=True)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_user_sessions_user_logged_in", "user_id", "logged_in_at"),
    )
