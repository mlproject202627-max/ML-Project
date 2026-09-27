import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


# Association table for many-to-many user-role relationship
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    department = Column(String(100))
    job_title = Column(String(255))
    status = Column(String(20), nullable=False, default="ACTIVE")
    # Banking-platform identity fields (spec §25): employee code + branch
    employee_code = Column(String(32), unique=True, nullable=True, index=True)  # e.g. EMP-10452
    branch_code = Column(String(32))    # e.g. VJA-CENTRAL
    branch_name = Column(String(120))   # e.g. Vijayawada Central
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    activities = relationship("Activity", back_populates="user")
    telemetry_events = relationship("TelemetryEvent", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    anomalies = relationship("Anomaly", back_populates="user", foreign_keys="Anomaly.user_id")
    risk_events = relationship("RiskEvent", back_populates="user")
    investigations = relationship("Investigation", back_populates="assigned_user", foreign_keys="Investigation.assigned_to")
    notifications = relationship("Notification", back_populates="user")

    # Detection foundation (spec §7, §8). `baseline` is consulted on every
    # telemetry write to decide whether an event falls outside working hours or
    # known locations, so it is a first-class relationship rather than a lookup.
    baseline = relationship(
        "EmployeeBaseline",
        back_populates="employee",
        uselist=False,
        foreign_keys="EmployeeBaseline.employee_id",
    )
    devices = relationship("Device", back_populates="employee", foreign_keys="Device.employee_id")
    risk_scores = relationship(
        "RiskScore",
        back_populates="employee",
        foreign_keys="RiskScore.employee_id",
        order_by="RiskScore.timestamp.desc()",
    )
    usb_events = relationship("UsbEvent", back_populates="employee", foreign_keys="UsbEvent.employee_id")


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
