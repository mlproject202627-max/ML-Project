"""Feature engineering: raw telemetry → the behavioral feature vector (spec §12).

One row per (employee, window). The columns are exactly the fifteen the spec
names, in a fixed order, because Isolation Forest is trained on a matrix and a
silently reordered column list would produce confident nonsense.

    Raw activity → [this module] → feature vector → Isolation Forest → anomaly score
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.resource import Resource, is_sensitive

#: Canonical column order. Never reorder without retraining.
FEATURE_NAMES: tuple[str, ...] = (
    "login_hour",
    "location_change",
    "country_change",
    "new_device",
    "failed_login_count",
    "records_accessed",
    "sensitive_records_accessed",
    "downloads",
    "download_volume",
    "usb_events",
    "after_hours",
    "session_duration",
    "unique_customers",
    "unique_resources",
    "department_access_count",
)

#: Human-readable labels for the explainability panel (spec §13).
FEATURE_LABELS: dict[str, str] = {
    "login_hour": "Login hour",
    "location_change": "Access from an unusual location",
    "country_change": "Access from an unusual country",
    "new_device": "Activity from a new device",
    "failed_login_count": "Failed login attempts",
    "records_accessed": "Total records accessed",
    "sensitive_records_accessed": "Sensitive records accessed",
    "downloads": "Documents downloaded",
    "download_volume": "Volume downloaded (MB)",
    "usb_events": "Removable-media events",
    "after_hours": "After-hours events",
    "session_duration": "Session duration (minutes)",
    "unique_customers": "Distinct customers touched",
    "unique_resources": "Distinct resources touched",
    "department_access_count": "Departments accessed",
}


@dataclass
class FeatureVector:
    """One employee-window observation."""

    login_hour: float = 0.0
    location_change: float = 0.0
    country_change: float = 0.0
    new_device: float = 0.0
    failed_login_count: float = 0.0
    records_accessed: float = 0.0
    sensitive_records_accessed: float = 0.0
    downloads: float = 0.0
    download_volume: float = 0.0
    usb_events: float = 0.0
    after_hours: float = 0.0
    session_duration: float = 0.0
    unique_customers: float = 0.0
    unique_resources: float = 0.0
    department_access_count: float = 0.0

    def to_list(self) -> list[float]:
        """Values in `FEATURE_NAMES` order."""
        data = asdict(self)
        return [float(data[name]) for name in FEATURE_NAMES]

    def to_dict(self) -> dict:
        return asdict(self)

    def top_contributors(self, reference: Optional["FeatureVector"] = None, limit: int = 5) -> list[dict]:
        """Rank features by how far they sit above a reference vector.

        This is the honest substitute for SHAP when no background dataset is
        available: it explains *what is unusual about this window relative to
        the employee's own baseline*, which is a claim we can actually support.
        """
        reference = reference or FeatureVector()
        base = asdict(reference)
        mine = asdict(self)

        scored: list[tuple[float, str, float, float]] = []
        for name in FEATURE_NAMES:
            observed = float(mine[name])
            expected = float(base[name])
            if observed <= 0:
                continue
            if expected <= 0:
                lift = observed  # something where the employee normally does nothing
            else:
                lift = (observed - expected) / expected
            if lift <= 0:
                continue
            scored.append((lift, name, observed, expected))

        scored.sort(reverse=True)
        return [
            {
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "value": round(observed, 2),
                "baseline": round(expected, 2),
                "lift": round(lift, 2),
            }
            for lift, name, observed, expected in scored[:limit]
        ]


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _download_volume_mb(events: Sequence[Activity]) -> float:
    """Sum the byte sizes recorded on download events, in megabytes.

    Sizes live in `metadata` because they vary by source. A missing size
    contributes nothing rather than a guessed average.
    """
    total = 0.0
    for event in events:
        meta = event.extra_metadata or {}
        size = meta.get("fileSize") or meta.get("file_size") or meta.get("sizeBytes")
        try:
            total += float(size or 0)
        except (TypeError, ValueError):
            continue
    return round(total / (1024 * 1024), 3)


def extract_features(
    events: Sequence[Activity],
    *,
    baseline=None,
    resource_departments: Optional[dict[str, str]] = None,
    now: Optional[datetime] = None,
) -> FeatureVector:
    """Build one employee-window feature vector. Pure — no database access."""
    if not events:
        return FeatureVector()

    resource_departments = resource_departments or {}
    ordered = sorted(events, key=lambda e: _aware(e.timestamp))

    login_hours = [
        _aware(e.timestamp).hour + _aware(e.timestamp).minute / 60.0
        for e in ordered
        if e.event_type == "LOGIN_SUCCESS"
    ]
    if not login_hours and baseline is not None and baseline.avg_login_hour is not None:
        login_hours = [float(baseline.avg_login_hour)]

    cities = {e.city for e in ordered if e.city}
    countries = {e.country for e in ordered if e.country}
    devices = {e.device for e in ordered if e.device}

    if baseline is not None:
        location_change = 0.0 if all(baseline.is_known_location(c) for c in cities) else 1.0
        known_countries = set((baseline.normal_countries or {}).keys())
        country_change = 0.0 if (not countries or countries <= known_countries) else 1.0
        new_device = 0.0 if all(baseline.is_known_device(d) for d in devices) else 1.0
    else:
        # Cold start: fall back to the per-event contextual flags the telemetry
        # recorder already computed against working hours.
        location_change = 1.0 if any((e.extra_metadata or {}).get("unusual_location") for e in ordered) else 0.0
        country_change = 0.0
        new_device = 1.0 if any((e.extra_metadata or {}).get("new_device") for e in ordered) else 0.0

    departments = {
        resource_departments[str(e.resource_id)]
        for e in ordered
        if e.resource_id and str(e.resource_id) in resource_departments
    }

    span_minutes = (_aware(ordered[-1].timestamp) - _aware(ordered[0].timestamp)).total_seconds() / 60.0

    return FeatureVector(
        login_hour=round(login_hours[0], 3) if login_hours else 0.0,
        location_change=location_change,
        country_change=country_change,
        new_device=new_device,
        failed_login_count=float(sum(1 for e in ordered if e.event_type == "LOGIN_FAILURE")),
        records_accessed=float(len(ordered)),
        sensitive_records_accessed=float(sum(1 for e in ordered if is_sensitive(e.sensitivity or "INTERNAL"))),
        downloads=float(sum(1 for e in ordered if e.event_type == "DOCUMENT_DOWNLOAD")),
        download_volume=_download_volume_mb(ordered),
        usb_events=float(sum(1 for e in ordered if e.event_type.startswith("USB_") or e.event_type == "SENSITIVE_FILE_TRANSFER")),
        after_hours=float(
            sum(1 for e in ordered if (e.extra_metadata or {}).get("after_hours") or e.event_type == "AFTER_HOURS_ACCESS")
        ),
        session_duration=round(max(0.0, span_minutes), 2),
        unique_customers=float(len({str(e.customer_id) for e in ordered if e.customer_id})),
        unique_resources=float(len({str(e.resource_id) for e in ordered if e.resource_id})),
        department_access_count=float(len(departments)),
    )


def collect_window(
    db: Session,
    *,
    employee_id,
    window_start: datetime,
    window_end: datetime,
) -> list[Activity]:
    return (
        db.query(Activity)
        .filter(
            Activity.user_id == employee_id,
            Activity.timestamp >= window_start,
            Activity.timestamp <= window_end,
        )
        .order_by(Activity.timestamp.asc())
        .all()
    )


def resource_department_map(db: Session, events: Sequence[Activity]) -> dict[str, str]:
    """One-query lookup of resource id → owning department."""
    resource_ids = {e.resource_id for e in events if e.resource_id}
    if not resource_ids:
        return {}
    rows = db.query(Resource.id, Resource.owner_department).filter(Resource.id.in_(resource_ids)).all()
    return {str(rid): dept for rid, dept in rows if dept}


def features_for_employee(
    db: Session,
    *,
    user,
    window_hours: int = 24,
    now: Optional[datetime] = None,
    baseline=None,
) -> FeatureVector:
    """Convenience wrapper: load the window, resolve departments, extract."""
    now = now or datetime.now(timezone.utc)
    events = collect_window(
        db,
        employee_id=user.id,
        window_start=now - timedelta(hours=window_hours),
        window_end=now,
    )
    return extract_features(
        events,
        baseline=baseline if baseline is not None else getattr(user, "baseline", None),
        resource_departments=resource_department_map(db, events),
        now=now,
    )
