"""Real-time behavioural telemetry from browsers and endpoint agents.

Every row is a moment in a user's activity: where they were, when it
happened, what device was involved, and what data was touched. Sources:
- `browser` — the Sentinel UI captures login time, view dwell, file
  uploads/drops, paired-USB device attach, and optional geolocation.
- `agent`   — the native endpoint daemon reports OS-level USB plug and
  file watch events, attributed to a user via an agent key.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # What kind of moment: LOGIN_TIME, LOGOUT_TIME, LOCATION_UPDATE,
    # USB_ATTACH, USB_ACCESS, FILE_UPLOAD, FILE_DROP, DATA_ACCESS,
    # VIEW_DWELL, HEARTBEAT
    event_type = Column(String(50), nullable=False, index=True)

    # Where the signal came from
    source = Column(String(20), nullable=False, default="browser")  # browser | agent

    # When
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Where (location signals)
    ip_address = Column(String(45))
    location = Column(String(255))
    latitude = Column(String(32))
    longitude = Column(String(32))
    accuracy_m = Column(Float)

    # What device / what data
    device = Column(String(255))       # e.g. USB stick serial/name, workstation id
    resource = Column(String(512))     # file path / page / resource label
    application = Column(String(255))

    # Free-form details: dwell seconds, file size, vendor/product ids, ...
    event_metadata = Column("metadata", JSON, default={})
    risk_contribution = Column(Float, default=0.0)

    user = relationship("User", back_populates="telemetry_events")

    __table_args__ = (
        Index("idx_telemetry_user_time", "user_id", "occurred_at"),
        Index("idx_telemetry_type", "event_type"),
    )
