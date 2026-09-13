import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(50), nullable=False)
    action = Column(String(255), nullable=False)
    resource = Column(String(255))
    source_ip = Column(String(45))
    device = Column(String(255))
    location = Column(String(255))
    application = Column(String(255))
    extra_metadata = Column("metadata", JSON, default={})
    risk_contribution = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="activities")
    anomalies = relationship("Anomaly", back_populates="activity")

    __table_args__ = (
        Index("idx_activities_user_id", "user_id"),
        Index("idx_activities_timestamp", "timestamp"),
        Index("idx_activities_event_type", "event_type"),
    )
