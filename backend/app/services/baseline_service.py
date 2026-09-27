"""Behavioural baseline service (spec §8).

Answers "what does a normal day look like for *this* employee?" and, given a
live window, "how far from that are they right now?".

The statistics live on the `EmployeeBaseline` model; this module is responsible
for *deriving* observations from telemetry and for scoring deviation.

Bucketing is done in Python rather than SQL on purpose: `date_trunc` (Postgres)
and `strftime` (SQLite) do not agree, and the tests run on SQLite while the app
runs on Postgres. One employee's 30-day history is a few thousand rows at most,
so the portability is free.
"""
from __future__ import annotations

import logging
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.baseline import EmployeeBaseline
from app.models.resource import Resource, is_sensitive

logger = logging.getLogger("sentinel.baseline")

#: How much history feeds a recomputation.
DEFAULT_HISTORY_DAYS = 30

#: Guards against dividing by zero on a quiet baseline.
VOLUME_FLOOR = 3.0

#: Working-hours envelope derived from observed logins.
WORK_WINDOW_SIGMA = 2.0
MIN_WORK_WINDOW_HOURS = 6.0
MAX_WORK_WINDOW_HOURS = 14.0

#: How much a never-before-seen location/device adds to the deviation score.
UNSEEN_LOCATION_PENALTY = 45.0
UNSEEN_DEVICE_PENALTY = 30.0

#: Event types whose `device` column holds removable-media, not a workstation.
REMOVABLE_MEDIA_EVENTS = frozenset({
    "USB_CONNECTED", "USB_DISCONNECTED", "FILE_TRANSFER_SIMULATED",
    "SENSITIVE_FILE_TRANSFER",
})


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fetch / create
# ---------------------------------------------------------------------------

def get_or_create_baseline(db: Session, user, *, commit: bool = True) -> EmployeeBaseline:
    baseline = db.query(EmployeeBaseline).filter(EmployeeBaseline.employee_id == user.id).first()
    if baseline is None:
        # Pass the object, not the id: `back_populates` then sets `user.baseline`
        # as well. The rule engine reads the relationship off the User, and a row
        # that exists only in the session would leave `user.baseline` as None for
        # the rest of the request — silently disabling every baseline-relative
        # rule (unusual location, unusual login hour, after-hours access) for a
        # first-ever session.
        baseline = EmployeeBaseline(employee=user, notes="auto-created on first observation")
        db.add(baseline)
        if commit:
            db.commit()
            db.refresh(baseline)
        else:
            db.flush()
    return baseline


def collect_history(
    db: Session, *, employee_id, days: int = DEFAULT_HISTORY_DAYS, now: Optional[datetime] = None
) -> list[Activity]:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    return (
        db.query(Activity)
        .filter(Activity.user_id == employee_id, Activity.timestamp >= since, Activity.timestamp <= now)
        .order_by(Activity.timestamp.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Observation derivation
# ---------------------------------------------------------------------------

def derive_observations(events: list[Activity], resource_departments: Optional[dict[str, str]] = None) -> dict:
    """Reduce a history window to the means and sets a baseline is built from.

    `resource_departments` maps `str(resource.id)` → owning department, so the
    baseline can learn which parts of the bank this employee normally works in
    without an N+1 query per event.
    """
    if not events:
        return {}

    resource_departments = resource_departments or {}

    per_day: dict[str, list[Activity]] = defaultdict(list)
    for event in events:
        per_day[_aware(event.timestamp).date().isoformat()].append(event)

    day_count = max(1, len(per_day))

    login_hours: list[float] = []
    locations: Counter = Counter()
    countries: Counter = Counter()
    devices: Counter = Counter()
    departments: Counter = Counter()

    total_sensitive = 0
    total_downloads = 0
    total_searches = 0
    unique_customers_per_day: list[int] = []
    unique_resources_per_day: list[int] = []

    for day_events in per_day.values():
        customers: set[str] = set()
        resources: set[str] = set()
        for event in day_events:
            ts = _aware(event.timestamp)
            if event.event_type == "LOGIN_SUCCESS":
                login_hours.append(ts.hour + ts.minute / 60.0)
            if event.city:
                locations[event.city] += 1
            if event.country:
                countries[event.country] += 1
            if event.device and event.event_type not in REMOVABLE_MEDIA_EVENTS:
                # Removable-media labels ride on `Activity.device` too. Learning
                # them here would make a USB stick look like one of the
                # employee's workstations and quietly familiarise the very thing
                # RULE-009 exists to catch.
                devices[event.device] += 1
            if event.customer_id:
                customers.add(str(event.customer_id))
            if event.resource_id:
                resources.add(str(event.resource_id))
                department = resource_departments.get(str(event.resource_id))
                if department:
                    departments[department] += 1
            if is_sensitive(event.sensitivity or "INTERNAL"):
                total_sensitive += 1
            if event.event_type in ("DOCUMENT_DOWNLOAD", "SENSITIVE_DATA_ACCESS"):
                total_downloads += 1
            if event.event_type == "CUSTOMER_SEARCH":
                total_searches += 1
        unique_customers_per_day.append(len(customers))
        unique_resources_per_day.append(len(resources))

    avg_login_hour = round(statistics.fmean(login_hours), 3) if login_hours else None
    login_stddev = round(statistics.pstdev(login_hours), 3) if len(login_hours) > 1 else None
    if login_stddev is not None:
        login_stddev = max(login_stddev, 0.5)  # never let a tight history make z-scores explode

    observations = {
        "avg_login_hour": avg_login_hour,
        "login_hour_stddev": login_stddev,
        "avg_daily_accesses": round(len(events) / day_count, 3),
        "avg_sensitive_accesses": round(total_sensitive / day_count, 3),
        "avg_downloads": round(total_downloads / day_count, 3),
        "avg_customer_searches": round(total_searches / day_count, 3),
        "avg_unique_customers": round(statistics.fmean(unique_customers_per_day), 3) if unique_customers_per_day else 0.0,
        "avg_unique_resources": round(statistics.fmean(unique_resources_per_day), 3) if unique_resources_per_day else 0.0,
        "locations": dict(locations),
        "countries": dict(countries),
        "devices": dict(devices),
        "departments": dict(departments),
        "days": day_count,
        "events": len(events),
    }
    return observations


def working_window(login_hours: list[float]) -> tuple[float, float]:
    """Derive a per-employee working-hours envelope from observed logins.

    Bounded so an odd week cannot declare a night shift "normal": the window is
    at least 6 hours and at most 14.
    """
    if not login_hours:
        return 9.0, 18.0
    mean = statistics.fmean(login_hours)
    spread = statistics.pstdev(login_hours) if len(login_hours) > 1 else 1.5
    spread = max(spread, 1.0)
    half = min(max(spread * WORK_WINDOW_SIGMA, MIN_WORK_WINDOW_HOURS / 2), MAX_WORK_WINDOW_HOURS / 2)
    start = max(0.0, mean - half)
    end = min(23.99, mean + half)
    if end - start < MIN_WORK_WINDOW_HOURS:
        end = min(23.99, start + MIN_WORK_WINDOW_HOURS)
    return round(start, 2), round(end, 2)


# ---------------------------------------------------------------------------
# Recompute
# ---------------------------------------------------------------------------

def recompute_baseline(
    db: Session,
    user,
    *,
    days: int = DEFAULT_HISTORY_DAYS,
    now: Optional[datetime] = None,
    commit: bool = True,
) -> EmployeeBaseline:
    """Re-derive this employee's baseline from their recent telemetry.

    Note this *blends* rather than replaces: `update_from_observations` caps how
    far one recomputation can move a mean, so a single anomalous fortnight
    cannot redefine the employee's normal.

    The learned sets are the exception — they are *rebased* from the window
    (`replace_sets=True`) rather than accumulated into. Means have a bounded
    step size and so are self-limiting; counts have none. Accumulating them on
    every recompute would make `normal_locations` a set that only ever grows,
    so a city visited once would remain "known" forever — the exact opposite of
    "a one-off location never becomes normal on its own".
    """
    now = now or datetime.now(timezone.utc)
    baseline = get_or_create_baseline(db, user, commit=False)
    events = collect_history(db, employee_id=user.id, days=days, now=now)

    # One query resolves every department this employee's activity touched.
    resource_ids = {e.resource_id for e in events if e.resource_id}
    resource_departments: dict[str, str] = {}
    if resource_ids:
        rows = db.query(Resource.id, Resource.owner_department).filter(Resource.id.in_(resource_ids)).all()
        resource_departments = {str(rid): dept for rid, dept in rows if dept}

    observations = derive_observations(events, resource_departments)

    if observations:
        # A first-ever computation must *seed* the baseline from the history
        # window. The row was just INSERTed, so the column defaults (0.0, 9.0)
        # have materialised on the instance and the bounded blend would read
        # "never observed" as a genuine zero, quartering every mean. From the
        # second computation onward the normal bounded blend applies.
        cold_start = (baseline.observed_days or 0) == 0 and (baseline.sample_events or 0) == 0
        baseline.update_from_observations(
            observations, replace_sets=True, max_adaptation=1.0 if cold_start else 0.25
        )

        login_hours = [
            _aware(e.timestamp).hour + _aware(e.timestamp).minute / 60.0
            for e in events
            if e.event_type == "LOGIN_SUCCESS"
        ]
        start, end = working_window(login_hours)
        baseline.work_start_hour = start
        baseline.work_end_hour = end

    if commit:
        db.commit()
        db.refresh(baseline)
    else:
        db.flush()
    return baseline


# ---------------------------------------------------------------------------
# Deviation scoring
# ---------------------------------------------------------------------------

def _volume_deviation(current: float, expected: float) -> float:
    """0 when at or below the expected volume; approaches 100 at 3× expected."""
    if expected <= VOLUME_FLOOR:
        # A light baseline still gets a meaningful reading, normalised against
        # the floor rather than against ~zero.
        expected = VOLUME_FLOOR
    ratio = current / expected
    if ratio <= 1.0:
        return 0.0
    return min(100.0, (ratio - 1.0) / 2.0 * 100.0)


def baseline_deviation(
    db: Session,
    user,
    *,
    window_start: datetime,
    window_end: datetime,
    baseline: Optional[EmployeeBaseline] = None,
) -> tuple[float, dict]:
    """Score how far the window's activity sits from the employee's own normal.

    Returns `(score_0_100, components)`. The score is the mean of the volume
    deviations, plus penalties for a never-before-seen location or device —
    those are categorical facts about the employee, not statistical drift.
    """
    baseline = baseline or get_or_create_baseline(db, user, commit=False)
    if (baseline.observed_days or 0) == 0 and (baseline.sample_events or 0) == 0:
        # Cold start: nothing to compare against. Reporting a deviation here
        # would be an invented number, so report none.
        return 0.0, {"cold_start": True}

    events = (
        db.query(Activity)
        .filter(
            Activity.user_id == user.id,
            Activity.timestamp >= window_start,
            Activity.timestamp <= window_end,
        )
        .all()
    )
    if not events:
        return 0.0, {"no_activity": True}

    sensitive = sum(1 for e in events if is_sensitive(e.sensitivity or "INTERNAL"))
    downloads = sum(1 for e in events if e.event_type in ("DOCUMENT_DOWNLOAD", "SENSITIVE_DATA_ACCESS"))
    searches = sum(1 for e in events if e.event_type == "CUSTOMER_SEARCH")
    customers = {str(e.customer_id) for e in events if e.customer_id}
    resources = {str(e.resource_id) for e in events if e.resource_id}

    components = {
        "accesses": _volume_deviation(len(events), baseline.avg_daily_accesses or 0.0),
        "sensitive": _volume_deviation(sensitive, baseline.avg_sensitive_accesses or 0.0),
        "downloads": _volume_deviation(downloads, baseline.avg_downloads or 0.0),
        "searches": _volume_deviation(searches, baseline.avg_customer_searches or 0.0),
        "uniqueCustomers": _volume_deviation(len(customers), baseline.avg_unique_customers or 0.0),
        "uniqueResources": _volume_deviation(len(resources), baseline.avg_unique_resources or 0.0),
    }

    volume_score = sum(components.values()) / len(components)

    unseen: list[str] = []
    for city in {e.city for e in events if e.city}:
        if not baseline.is_known_location(city):
            unseen.append(city)
    if unseen:
        volume_score = min(100.0, volume_score + UNSEEN_LOCATION_PENALTY)
        components["unseenLocations"] = unseen

    unseen_devices = [
        label for label in {e.device for e in events if e.device} if not baseline.is_known_device(label)
    ]
    if unseen_devices:
        volume_score = min(100.0, volume_score + UNSEEN_DEVICE_PENALTY)
        components["unseenDevices"] = unseen_devices

    return round(min(100.0, volume_score), 2), components
