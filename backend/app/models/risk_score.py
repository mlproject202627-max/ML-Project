"""Point-in-time composite risk score per employee.

One row per scoring run. Keeping history (rather than only "current score")
is what lets the admin UI draw a risk trend and show what changed between
two assessments.

Levels (spec §11):
    0–20   LOW
    21–40  MODERATE
    41–60  ELEVATED
    61–80  HIGH
    81–100 CRITICAL
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


#: (lower_bound_inclusive, level) — evaluated high → low.
RISK_BANDS = [
    (81, "CRITICAL"),
    (61, "HIGH"),
    (41, "ELEVATED"),
    (21, "MODERATE"),
    (0, "LOW"),
]

RISK_LEVELS = ["LOW", "MODERATE", "ELEVATED", "HIGH", "CRITICAL"]

#: Display colour per level, shared with the frontend via the API.
RISK_LEVEL_COLOR = {
    "LOW": "#737373",
    "MODERATE": "#2563EB",
    "ELEVATED": "#D97706",
    "HIGH": "#EA580C",
    "CRITICAL": "#DC2626",
}


def level_for_score(score: float) -> str:
    """Map a 0–100 score onto its named level."""
    value = max(0.0, min(100.0, float(score or 0.0)))
    for threshold, level in RISK_BANDS:
        if value >= threshold:
            return level
    return "LOW"


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    current_score = Column(Float, nullable=False, default=0.0, index=True)
    previous_score = Column(Float, nullable=True)
    change = Column(Float, nullable=False, default=0.0)
    risk_level = Column(String(16), nullable=False, default="LOW", index=True)

    # Breakdown of what produced the score — the explainability payload.
    # [{"source": "RULE", "code": "RULE-007", "label": "...", "contribution": 15.0}, ...]
    reasons = Column(JSON, default=list)

    # Component subtotals so the UI can show "rules 45 · ML 22 · baseline 14"
    rule_score = Column(Float, nullable=False, default=0.0)
    ml_score = Column(Float, nullable=False, default=0.0)
    baseline_score = Column(Float, nullable=False, default=0.0)

    # Window the score summarises
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)

    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    note = Column(Text)

    employee = relationship("User", back_populates="risk_scores", foreign_keys=[employee_id])

    __table_args__ = (
        Index("idx_risk_scores_employee_time", "employee_id", "timestamp"),
        Index("idx_risk_scores_level", "risk_level"),
    )
