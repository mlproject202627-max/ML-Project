import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    activity_id = Column(UUID(as_uuid=True), ForeignKey("activities.id"), nullable=True)
    detection_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    risk_score = Column(Float, nullable=False)
    anomaly_score = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    description = Column(String(1000))
    status = Column(String(20), nullable=False, default="OPEN")
    detected_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="anomalies")
    activity = relationship("Activity", back_populates="anomalies")
    risk_events = relationship("RiskEvent", back_populates="anomaly")
    investigations = relationship("Investigation", back_populates="anomaly")
    notification = relationship("Notification", back_populates="anomaly", uselist=False)

    __table_args__ = (
        Index("idx_anomalies_user_id", "user_id"),
        Index("idx_anomalies_severity", "severity"),
        Index("idx_anomalies_status", "status"),
        Index("idx_anomalies_detected_at", "detected_at"),
    )
