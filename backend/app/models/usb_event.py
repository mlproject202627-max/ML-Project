"""Simulated USB activity (academic demonstration only).

IMPORTANT — this is a *simulation*, not endpoint surveillance.

The Sentinel demo never inspects a real machine's USB bus. Instead, the
employee portal offers a "Simulate Device Activity" control and the endpoint
agent reports OS-visible attach events; both paths land here so the detection
engine has a realistic, consent-safe stand-in for removable-media activity.

Sequence modelled: CONNECT → TRANSFER (one per file) → DISCONNECT.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


USB_ACTIONS = {"CONNECT", "DISCONNECT", "TRANSFER"}


class UsbEvent(Base):
    __tablename__ = "usb_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # "USB-DEMO-1024" — stable label so repeats on the same stick are recognisable
    device_label = Column(String(80), nullable=False, index=True)

    action = Column(String(16), nullable=False, index=True)  # CONNECT / DISCONNECT / TRANSFER

    # Only meaningful for TRANSFER
    file_name = Column(String(255))
    file_size = Column(Integer)                              # bytes
    classification = Column(String(24))                      # classification of the file moved

    # Link back to the registry row when the transfer targeted a known resource
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id"), nullable=True, index=True)

    occurred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    notes = Column(Text)

    employee = relationship("User", back_populates="usb_events", foreign_keys=[employee_id])
    resource = relationship("Resource", foreign_keys=[resource_id])

    __table_args__ = (
        Index("idx_usb_events_employee_time", "employee_id", "occurred_at"),
        Index("idx_usb_events_action", "action"),
    )
