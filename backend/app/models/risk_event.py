import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    anomaly_id = Column(UUID(as_uuid=True), ForeignKey("anomalies.id"), nullable=True)
    signal_type = Column(String(50), nullable=False)
    signal_value = Column(Float, nullable=False)
    weight = Column(Float, nullable=False)
    contribution = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="risk_events")
    anomaly = relationship("Anomaly", back_populates="risk_events")

    __table_args__ = (
        Index("idx_risk_events_user_id", "user_id"),
    )
