"""Workstations, laptops and mobile devices an employee uses.

Devices are learned from telemetry: the first time an employee is seen from a
given fingerprint the row is created with `is_trusted=False` and `is_new=True`.
Once the device appears consistently it becomes trusted, which is what lets the
"new device" rule distinguish a genuine first-seen device from routine use.

No invasive fingerprinting: the fingerprint is a coarse, client-reported
identifier (user-agent family + platform + screen class) combined into a hash.
"""
import uuid
import hashlib
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def build_fingerprint(user_agent: str, platform: str = "", screen: str = "") -> str:
    """Coarse, non-invasive device fingerprint.

    Deliberately low-entropy: we want to recognise "the same kind of machine",
    not to single out a physical unit for surveillance.
    """
    raw = "|".join([
        (user_agent or "unknown")[:180],
        (platform or "unknown")[:60],
        (screen or "unknown")[:40],
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(40), unique=True, nullable=False, index=True)  # DEVICE-A1024
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    label = Column(String(120))              # "Chrome on Windows — Branch desktop"
    device_type = Column(String(24), default="WORKSTATION")  # WORKSTATION / LAPTOP / MOBILE / TABLET
    operating_system = Column(String(80))
    browser = Column(String(80))
    fingerprint = Column(String(64), index=True)

    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    seen_count = Column(Integer, nullable=False, default=1)

    is_trusted = Column(Boolean, nullable=False, default=False)
    is_new = Column(Boolean, nullable=False, default=True)

    employee = relationship("User", back_populates="devices", foreign_keys=[employee_id])

    __table_args__ = (
        Index("idx_devices_employee", "employee_id"),
        Index("idx_devices_fingerprint_employee", "employee_id", "fingerprint"),
    )
