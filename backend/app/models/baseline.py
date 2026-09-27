"""Per-employee behavioural baseline.

The baseline answers "what does normal look like for THIS person?". Detection
compares live activity against it rather than against a global average, which
is what keeps a branch teller's normal day from looking like an anomaly.

Two design rules, both deliberate:

1. **Slow adaptation.** `update_from_observations` blends the new observation
   into the stored mean with a bounded weight (`max_adaptation`). One abnormal
   day therefore moves the baseline only slightly — a single burst of theft
   cannot launder itself into "normal" in one step.

2. **Robust statistics.** Means are exponential moving averages seeded from a
   history window; locations/devices are *sets* with counts so that a one-off
   location never becomes "normal" on its own.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class EmployeeBaseline(Base):
    __tablename__ = "employee_baselines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # -- login rhythm ------------------------------------------------------
    avg_login_hour = Column(Float, default=9.0)          # 9.5 == 09:30
    login_hour_stddev = Column(Float, default=1.0)
    work_start_hour = Column(Float, default=9.0)
    work_end_hour = Column(Float, default=18.0)

    # -- volume per active day --------------------------------------------
    avg_daily_accesses = Column(Float, default=0.0)
    avg_sensitive_accesses = Column(Float, default=0.0)
    avg_downloads = Column(Float, default=0.0)
    avg_customer_searches = Column(Float, default=0.0)
    avg_unique_customers = Column(Float, default=0.0)
    avg_unique_resources = Column(Float, default=0.0)

    # -- session shape -----------------------------------------------------
    typical_session_minutes = Column(Float, default=0.0)

    # -- learned sets (JSON because these are small, bounded, read-whole lists)
    #    {"Vijayawada": 42, "Hyderabad": 3}
    normal_locations = Column(JSON, default=dict)
    #    {"IN": 45}
    normal_countries = Column(JSON, default=dict)
    #    {"DEVICE-A1024": 30}
    normal_devices = Column(JSON, default=dict)
    #    {"Retail Banking": 20}
    typical_departments = Column(JSON, default=dict)

    # -- provenance --------------------------------------------------------
    observed_days = Column(Integer, nullable=False, default=0)
    sample_events = Column(Integer, nullable=False, default=0)
    last_computed_at = Column(DateTime(timezone=True), default=_now)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    notes = Column(String(500))

    employee = relationship("User", back_populates="baseline", foreign_keys=[employee_id])

    __table_args__ = (
        Index("idx_baselines_employee", "employee_id"),
    )

    # -- behaviour ---------------------------------------------------------

    def is_known_location(self, city: str | None, country: str | None = None) -> bool:
        if not city:
            return True
        if city in (self.normal_locations or {}):
            return True
        if country and country in (self.normal_countries or {}):
            return True
        return False

    def is_known_device(self, device_id: str | None) -> bool:
        if not device_id:
            return True
        return device_id in (self.normal_devices or {})

    def is_within_working_hours(self, hour: float) -> bool:
        """True when `hour` (0–23.99 float) sits in the employee's normal window."""
        start = self.work_start_hour if self.work_start_hour is not None else 9.0
        end = self.work_end_hour if self.work_end_hour is not None else 18.0
        return start <= hour <= end

    def login_hour_zscore(self, hour: float) -> float:
        """How far outside the normal login hour, in standard deviations."""
        sd = self.login_hour_stddev or 1.0
        if sd <= 0:
            sd = 1.0
        mean = self.avg_login_hour if self.avg_login_hour is not None else 9.0
        return abs(hour - mean) / sd

    def update_from_observations(
        self,
        observations: dict,
        *,
        max_adaptation: float = 0.25,
        replace_sets: bool = False,
    ) -> None:
        """Blend a day's observations into the baseline.

        `max_adaptation` caps how much any single update can move a mean. With
        the default 0.25, one extreme day shifts a mean at most a quarter of the
        way toward it — repeated days are required to redefine "normal".

        `replace_sets` decides what happens to the learned location/device sets:

        - `False` (incremental): counts accumulate, for callers folding in one
          day at a time.
        - `True` (rebase): the sets become exactly what the observation window
          contains. Use this when the observations were derived from a rolling
          history window, because accumulating them instead makes the sets
          monotonically expand — a location visited once would stay "normal"
          forever, with a count that only grows, which is the opposite of what
          the class promises.
        """
        if not observations:
            return

        def blend(current, new, weight=max_adaptation):
            if new is None:
                return current
            if current is None:
                return new
            w = min(max(weight, 0.0), 1.0)
            return round(current * (1 - w) + new * w, 4)

        self.avg_login_hour = blend(self.avg_login_hour, observations.get("avg_login_hour"))
        self.login_hour_stddev = blend(self.login_hour_stddev, observations.get("login_hour_stddev"), 0.15)
        self.avg_daily_accesses = blend(self.avg_daily_accesses, observations.get("avg_daily_accesses"))
        self.avg_sensitive_accesses = blend(self.avg_sensitive_accesses, observations.get("avg_sensitive_accesses"))
        self.avg_downloads = blend(self.avg_downloads, observations.get("avg_downloads"))
        self.avg_customer_searches = blend(self.avg_customer_searches, observations.get("avg_customer_searches"))
        self.avg_unique_customers = blend(self.avg_unique_customers, observations.get("avg_unique_customers"))
        self.avg_unique_resources = blend(self.avg_unique_resources, observations.get("avg_unique_resources"))
        self.typical_session_minutes = blend(
            self.typical_session_minutes, observations.get("typical_session_minutes"), 0.15
        )

        # Sets describe what this employee does *habitually*. On a rebase they
        # are taken from the window as-is; incrementally they accumulate, so a
        # location/device becomes "normal" through repetition rather than a
        # single appearance.
        for field, key in (
            ("normal_locations", "locations"),
            ("normal_countries", "countries"),
            ("normal_devices", "devices"),
            ("typical_departments", "departments"),
        ):
            incoming = observations.get(key) or {}
            if not incoming and not replace_sets:
                continue
            if replace_sets:
                setattr(self, field, {
                    name: int(count or 1) for name, count in incoming.items() if name
                })
                continue
            current = dict(getattr(self, field) or {})
            for name, count in incoming.items():
                if not name:
                    continue
                current[name] = current.get(name, 0) + int(count or 1)
            setattr(self, field, current)

        self.observed_days = (self.observed_days or 0) + int(observations.get("days", 1) or 1)
        self.sample_events = (self.sample_events or 0) + int(observations.get("events", 0) or 0)
        self.last_computed_at = _now()

    def to_dict(self) -> dict:
        """Serialisable summary for the admin API."""
        return {
            "employee_id": str(self.employee_id),
            "avg_login_hour": self.avg_login_hour,
            "login_hour_stddev": self.login_hour_stddev,
            "work_start_hour": self.work_start_hour,
            "work_end_hour": self.work_end_hour,
            "avg_daily_accesses": self.avg_daily_accesses,
            "avg_sensitive_accesses": self.avg_sensitive_accesses,
            "avg_downloads": self.avg_downloads,
            "avg_customer_searches": self.avg_customer_searches,
            "typical_session_minutes": self.typical_session_minutes,
            "normal_locations": self.normal_locations or {},
            "normal_countries": self.normal_countries or {},
            "normal_devices": self.normal_devices or {},
            "typical_departments": self.typical_departments or {},
            "observed_days": self.observed_days,
            "sample_events": self.sample_events,
            "last_computed_at": self.last_computed_at.isoformat() if self.last_computed_at else None,
        }
