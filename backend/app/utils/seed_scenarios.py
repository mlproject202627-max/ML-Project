"""Demo history generation and the eight security scenarios (spec §26, §27).

Two responsibilities:

`seed_history()` writes ~30 days of *normal* banking activity for every demo
employee. This exists because the detection layer needs something to learn
"normal" from — without it every baseline is empty, every deviation is
undefined and the Isolation Forest has nothing to train on.

`run_scenario(name)` injects one of the eight scripted behaviours from spec §27
and returns the resulting assessment, so the demo can show the score climbing
and an alert appearing without anyone hand-editing the database.

All data is synthetic. Location values are city names attached to the demo
branches — approximate by construction, never coordinates.
"""
from __future__ import annotations

import hashlib
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.activity import Activity
from app.models.banking import Customer
from app.models.device import Device
from app.models.resource import Resource
from app.models.user import User

logger = logging.getLogger("sentinel.scenarios")

#: Days of history to synthesise.
HISTORY_DAYS = 30

#: Device the rogue scenarios authenticate from — a workstation this employee
#: has never used.
ROGUE_DEVICE = "DEVICE-X9999"

#: Removable media label used by the simulated USB transfer. This is not a
#: workstation and deliberately never becomes a `Device` row.
USB_MEDIA = "USB-DEMO-1024"

#: Demo employees and their working patterns. Keyed by email so the seed is
#: stable across database rebuilds.
EMPLOYEE_PATTERNS = {
    "meera.krishnan@sentinel.in": {
        "login_hour": 9.5, "logout_hour": 17.5, "searches": 22, "views": 14,
        "transactions": 8, "documents": 2, "city": "Vijayawada", "device": "DEVICE-A1024",
    },
    "arjun.nair@sentinel.in": {
        "login_hour": 9.0, "logout_hour": 18.5, "searches": 30, "views": 20,
        "transactions": 10, "documents": 3, "city": "Vijayawada", "device": "DEVICE-B1024",
    },
    "sunita.rao@sentinel.in": {
        "login_hour": 8.75, "logout_hour": 19.0, "searches": 12, "views": 9,
        "transactions": 5, "documents": 1, "city": "Hyderabad", "device": "DEVICE-C1024",
    },
    "farhan.ali@sentinel.in": {
        "login_hour": 9.25, "logout_hour": 18.0, "searches": 6, "views": 5,
        "transactions": 2, "documents": 6, "city": "Vijayawada", "device": "DEVICE-D1024",
    },
    "deepak.menon@sentinel.in": {
        "login_hour": 9.75, "logout_hour": 18.25, "searches": 9, "views": 7,
        "transactions": 12, "documents": 2, "city": "Visakhapatnam", "device": "DEVICE-E1024",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_seed(text: str) -> int:
    """A reproducible seed.

    `hash()` is salted per process by PYTHONHASHSEED, so using it here would
    make a scenario produce different synthetic customers on every restart —
    unacceptable when the point is to demo the same storyline twice.
    """
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


# ---------------------------------------------------------------------------
# Normal history
# ---------------------------------------------------------------------------

def seed_history(db: Session | None = None, *, days: int = HISTORY_DAYS, force: bool = False) -> int:
    """Generate normal working activity for the demo employees.

    Idempotent: skipped when activity already spans a meaningful history, unless
    `force` is set.
    """
    owns_session = db is None
    db = db or SessionLocal()
    written = 0
    try:
        existing = db.query(Activity).count()
        if existing > 200 and not force:
            logger.info("History already present (%d events); skipping generation.", existing)
            return 0

        from app.core.dependencies import EMPLOYEE_ROLES, role_names
        from app.services.telemetry import allocate_device_label

        # Only banking staff get a synthetic history. Admin and security accounts
        # are not portal users; inventing a working pattern for them would put
        # fictional activity against their names in the security timeline.
        employees = [
            user for user in db.query(User).all() if role_names(user) & EMPLOYEE_ROLES
        ]
        if not employees:
            logger.info("No employees to generate history for.")
            return 0

        customers = db.query(Customer).all()
        customer_ids = [c.id for c in customers]
        if not customer_ids:
            logger.warning("No customers seeded; cannot generate realistic history.")
            return 0
        customers_by_id = {c.id: c for c in customers}

        rng = random.Random(20260927)

        from app.services.baseline_service import get_or_create_baseline
        from app.services.telemetry import record_event, simulated_device

        now = _now()

        for employee in employees:
            pattern = EMPLOYEE_PATTERNS.get(employee.email)
            if pattern is None:
                # A non-demo account. Give it a light pattern rather than
                # nothing, so its baseline is not empty. The device label is
                # allocated rather than hard-coded: `Device.device_id` is
                # globally unique, so a shared literal would collide the moment
                # two employees fell through to this branch.
                pattern = {
                    "login_hour": 9.5, "logout_hour": 18.0, "searches": 5, "views": 4,
                    "transactions": 2, "documents": 1,
                    "city": (employee.branch_name or "Vijayawada").split(" ")[0],
                    "device": allocate_device_label(db, employee),
                }

            baseline = get_or_create_baseline(db, employee, commit=False)
            # Register the device row too, not just the label. Without it the
            # device table stays empty while the activity table refers to it, and
            # a later scenario re-registering the same label would look like a
            # brand-new device.
            device = simulated_device(db, employee, pattern["device"], is_new=False)

            for day_offset in range(days, 0, -1):
                day = now - timedelta(days=day_offset)
                if day.weekday() >= 5 and rng.random() < 0.85:
                    continue  # most weekends are quiet

                login_at = day.replace(
                    hour=int(pattern["login_hour"]),
                    minute=rng.randint(0, 45),
                    second=0, microsecond=0,
                )
                if login_at > now:
                    continue

                # A small share of days are lighter or heavier than usual; a
                # baseline built only from identical days would be unrealistically
                # tight and would flag ordinary variation.
                jitter = rng.uniform(0.7, 1.3)

                events = _day_script(pattern, rng, jitter, customer_ids)
                cursor = login_at

                record_event(
                    db, user=employee, action="login_success", event_type="LOGIN_SUCCESS",
                    city=pattern["city"], country="IN", device=device,
                    occurred_at=cursor, baseline=baseline, run_detection=False, commit=False,
                )
                written += 1

                for action, event_type, resource_label, sensitivity, customer_id in events:
                    cursor = cursor + timedelta(minutes=rng.uniform(4, 26))
                    if cursor.hour >= pattern["logout_hour"]:
                        break
                    customer = customers_by_id.get(customer_id) if customer_id else None
                    record_event(
                        db, user=employee, action=action, event_type=event_type,
                        resource_label=resource_label, sensitivity=sensitivity,
                        customer=customer,
                        city=pattern["city"], country="IN", device=device,
                        occurred_at=cursor, baseline=baseline,
                        run_detection=False, commit=False,
                    )
                    written += 1

                    if written % 400 == 0:
                        db.commit()

                cursor = cursor + timedelta(minutes=rng.uniform(2, 20))
                record_event(
                    db, user=employee, action="logout", event_type="LOGOUT",
                    city=pattern["city"], country="IN", device=device,
                    occurred_at=cursor, baseline=baseline, run_detection=False, commit=False,
                )
                written += 1

            db.commit()

        logger.info("Generated %d historical activity events.", written)

        # Derive each employee's baseline and the ML model from what we just wrote.
        from app.services.baseline_service import recompute_baseline
        for employee in employees:
            recompute_baseline(db, employee, days=days, commit=True)

        _train_model(db)

        return written
    except Exception as exc:
        logger.warning("History generation failed: %s", exc)
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


def _day_script(pattern: dict, rng: random.Random, jitter: float, customer_ids: list) -> list[tuple]:
    """Build one day's event list.

    Each entry is `(action, event_type, resource_label, sensitivity, customer_id)`;
    the caller unpacks it into `record_event`. Events are shuffled because a
    realistic day is not sorted by activity type, and `RULE-008` (rapid sweep)
    would fire spuriously on any run of same-type events.
    """
    events: list[tuple] = []

    for _ in range(max(0, int(pattern["searches"] * jitter))):
        events.append(("customer_search", "CUSTOMER_SEARCH", "customer-search", "INTERNAL", None))

    for _ in range(max(0, int(pattern["views"] * jitter))):
        cid = rng.choice(customer_ids)
        events.append(("customer_profile_view", "CUSTOMER_VIEW", "customer-record", "CONFIDENTIAL", cid))

    for _ in range(max(0, int(pattern["transactions"] * jitter))):
        cid = rng.choice(customer_ids)
        events.append(("transaction_history_view", "TRANSACTION_VIEW", "account-statement", "CONFIDENTIAL", cid))

    for _ in range(max(0, int(pattern["documents"] * jitter))):
        cid = rng.choice(customer_ids)
        events.append(("document_download", "DOCUMENT_DOWNLOAD", "kyc-document", "CONFIDENTIAL", cid))

    rng.shuffle(events)
    return events


def _train_model(db: Session) -> None:
    """Train the Isolation Forest on the freshly generated history."""
    try:
        from ml.anomaly import train_from_telemetry

        detector = train_from_telemetry(db, days=HISTORY_DAYS)
        if detector is None:
            logger.info("Isolation Forest not trained — insufficient history.")
        else:
            logger.info("Isolation Forest trained on %d employee-days.", detector.training_rows)
    except Exception as exc:
        logger.warning("ML training skipped: %s", exc)


# ---------------------------------------------------------------------------
# Scenarios (spec §27)
# ---------------------------------------------------------------------------

SCENARIOS = {
    "normal": "Ordinary working day — no rules should fire.",
    "after_hours": "Sensitive access at 02:20 from the employee's usual device.",
    "new_device": "Access from an unrecognised device fingerprint.",
    "unusual_location": "Access from a city this employee has never used.",
    "mass_lookup": "Bulk customer-record enumeration.",
    "sensitive_download": "Repeated downloads of highly confidential documents.",
    "usb_transfer": "Copy of a sensitive file to removable media (simulated).",
    "combined_insider": "Coordinated theft: off-hours + new device + foreign city + mass lookup + downloads + USB.",
}


def _resolve_employee(db: Session, email: Optional[str]) -> User:
    if email:
        employee = db.query(User).filter(User.email == email).first()
        if employee is None:
            raise ValueError(f"No employee with email {email}")
        return employee
    employee = db.query(User).filter(User.email == "arjun.nair@sentinel.in").first()
    if employee is None:
        employee = db.query(User).first()
    if employee is None:
        raise ValueError("No employees exist to run a scenario against")
    return employee


def _confidential_resources(db: Session, limit: int = 8) -> list[Resource]:
    """The most sensitive resources, most restrictive first.

    Ranking is done in Python against the explicit classification ladder rather
    than `ORDER BY classification DESC`. The latter would sort alphabetically and
    happen to give the right answer for today's five labels — a coincidence that
    would silently invert the moment a classification name changed.
    """
    from app.models.resource import SENSITIVE_CLASSIFICATIONS, classification_rank

    candidates = (
        db.query(Resource)
        .filter(Resource.classification.in_(sorted(SENSITIVE_CLASSIFICATIONS)))
        .all()
    )
    candidates.sort(key=lambda r: classification_rank(r.classification), reverse=True)
    return candidates[:limit]


def _scenario_volumes(baseline, population: int) -> dict:
    """Event volumes that actually exceed the thresholds a scenario demonstrates.

    Read from the rule engine rather than hard-coded. A demo emitting 35 searches
    against a threshold of 90 is not a failing rule — it is a failing
    demonstration, and from the dashboard it looks exactly like a broken
    detector.
    """
    from ml import rule_engine as rules

    search_threshold = rules.search_burst_threshold(baseline)
    distinct_threshold, _ = rules.mass_access_threshold(baseline, population)

    warnings: list[str] = []
    distinct = int(distinct_threshold) + 2
    if distinct > population:
        warnings.append(
            f"Only {population} customer records exist but RULE-005 needs "
            f"{distinct_threshold:.0f} distinct accesses, so this run cannot trip "
            f"it. Seed more customers for a complete demonstration."
        )
        distinct = population

    return {
        "searchCount": int(search_threshold) + 5,
        "customerCount": distinct,
        "searchThreshold": round(search_threshold, 1),
        "distinctThreshold": round(distinct_threshold, 1),
        "warnings": warnings,
    }


def run_scenario(
    db: Session,
    name: str,
    *,
    email: Optional[str] = None,
    reset: bool = True,
    actor=None,
) -> dict:
    """Inject one scripted scenario and return the resulting detection state.

    Events are written *without* per-event detection and the risk engine is run
    at a few checkpoints instead. Scoring each of the ~38 combined-scenario
    events individually would repeat the same 24-hour window analysis 38 times
    for one answer, and the checkpoints are what actually produce the
    progressive LOW → MODERATE → HIGH → CRITICAL story the demo needs.

    `reset` clears the employee's carried risk first, so each scenario's result
    is attributable to that scenario. Because scores decay over 24 hours, a
    scenario replayed against a previously-used employee would otherwise inherit
    the earlier score and demonstrate nothing.
    """
    key = (name or "").strip().lower()
    if key not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{name}'. Available: {', '.join(sorted(SCENARIOS))}")

    employee = _resolve_employee(db, email)
    rng = random.Random(_stable_seed(key))

    from app.services import detection
    from app.services.baseline_service import get_or_create_baseline
    from app.services.telemetry import allocate_device_label, record_event, simulated_device

    reset_info = None
    if reset:
        reset_info = detection.reset_risk(
            db, employee, actor=actor,
            reason=f"Cleared before demo scenario '{key}'",
        )

    baseline = get_or_create_baseline(db, employee, commit=False)
    pattern = EMPLOYEE_PATTERNS.get(employee.email, {})
    home_city = pattern.get("city") or (employee.branch_name or "Vijayawada").split(" ")[0]
    now = _now()
    customers = db.query(Customer).all()
    resources = _confidential_resources(db)

    # The employee's everyday device is whatever they actually use most, taken
    # from the device table rather than assumed from the demo pattern — so a
    # scenario works against any employee, including ones added later.
    home_device = (
        db.query(Device)
        .filter(Device.employee_id == employee.id, Device.is_new.is_(False))
        .order_by(Device.seen_count.desc())
        .first()
    )
    if home_device is None:
        home_device = simulated_device(
            db, employee,
            pattern.get("device") or allocate_device_label(db, employee),
            is_new=False,
        )

    volumes = _scenario_volumes(baseline, len(customers))
    warnings: list[str] = list(volumes["warnings"])

    # Register the rogue device so the scenario exercises the real NEW_DEVICE
    # path instead of asserting the flag itself.
    rogue_device = simulated_device(db, employee, ROGUE_DEVICE, is_new=True)

    progression: list[dict] = []
    last_result: Optional[dict] = None

    def emit(action, event_type, **kwargs):
        record_event(
            db, user=employee, action=action, event_type=event_type,
            baseline=baseline, run_detection=False, commit=False, **kwargs,
        )

    def checkpoint(label: str) -> dict:
        """Score the window so far and remember the step for the demo replay."""
        nonlocal last_result
        db.commit()
        last_result = detection.evaluate_employee(db, employee, commit=True)
        assessment = last_result["assessment"]
        progression.append({
            "step": label,
            "score": assessment.score,
            "level": assessment.level,
            "rules": [hit.rule_id for hit in assessment.rule_hits],
        })
        return last_result

    if key == "normal":
        emit("login_success", "LOGIN_SUCCESS", city=home_city, country="IN",
             device=home_device, occurred_at=now - timedelta(hours=1))
        for _ in range(6):
            emit("customer_search", "CUSTOMER_SEARCH", city=home_city, country="IN",
                 device=home_device, occurred_at=now - timedelta(minutes=rng.randint(5, 50)))
        emit("logout", "LOGOUT", city=home_city, country="IN",
             device=home_device, occurred_at=now)

    elif key == "after_hours":
        # 02:20 local — well outside this employee's 09:00–18:00 envelope.
        night = now.replace(hour=2, minute=20, second=0, microsecond=0)
        emit("login_success", "LOGIN_SUCCESS", city=home_city, country="IN",
             device=home_device, occurred_at=night)
        for index, resource in enumerate(resources[:3]):
            emit("sensitive_access", "SENSITIVE_DATA_ACCESS", resource=resource,
                 city=home_city, country="IN", device=home_device,
                 occurred_at=night + timedelta(minutes=6 * index + 3))

    elif key == "new_device":
        emit("login_success", "LOGIN_SUCCESS", city=home_city, country="IN",
             device=rogue_device, occurred_at=now - timedelta(minutes=20))
        for _ in range(6):
            emit("customer_profile_view", "CUSTOMER_VIEW",
                 customer=rng.choice(customers) if customers else None,
                 city=home_city, country="IN", device=rogue_device,
                 occurred_at=now - timedelta(minutes=rng.randint(2, 18)))

    elif key == "unusual_location":
        emit("login_success", "LOGIN_SUCCESS", city="Bengaluru", country="IN",
             device=home_device, occurred_at=now - timedelta(minutes=30))
        for _ in range(5):
            emit("customer_profile_view", "CUSTOMER_VIEW",
                 customer=rng.choice(customers) if customers else None,
                 city="Bengaluru", country="IN", device=home_device,
                 occurred_at=now - timedelta(minutes=rng.randint(2, 25)))

    elif key == "mass_lookup":
        for index in range(volumes["searchCount"]):
            emit("customer_search", "CUSTOMER_SEARCH", city=home_city, country="IN",
                 device=home_device, occurred_at=now - timedelta(seconds=40 * index))
        for index, customer in enumerate(customers[: volumes["customerCount"]]):
            emit("customer_profile_view", "CUSTOMER_VIEW", customer=customer,
                 city=home_city, country="IN", device=home_device,
                 occurred_at=now - timedelta(seconds=30 * index))

    elif key == "sensitive_download":
        for index, resource in enumerate(resources[:6]):
            emit("document_download", "DOCUMENT_DOWNLOAD", resource=resource,
                 city=home_city, country="IN", device=home_device,
                 occurred_at=now - timedelta(minutes=3 * index))

    elif key == "usb_transfer":
        # `device_label` here is removable-media, not a workstation — the USB
        # label deliberately does not become a Device row.
        target = resources[0] if resources else None
        emit("usb_connected", "USB_CONNECTED", device_label=USB_MEDIA,
             city=home_city, country="IN", occurred_at=now - timedelta(minutes=6))
        emit("sensitive_file_transfer", "SENSITIVE_FILE_TRANSFER", resource=target,
             device_label=USB_MEDIA, city=home_city, country="IN",
             severity="CRITICAL",
             metadata={
                 "fileName": target.file_name if target else "customer_risk_report.pdf",
                 "fileSize": (target.file_size if target else 1_887_436),
                 "classification": target.classification if target else "HIGHLY_CONFIDENTIAL",
             },
             occurred_at=now - timedelta(minutes=4))
        emit("usb_disconnected", "USB_DISCONNECTED", device_label=USB_MEDIA,
             city=home_city, country="IN", occurred_at=now - timedelta(minutes=2))

    elif key == "combined_insider":
        # A single narrative in four acts, scored at each boundary so the
        # dashboard can show risk climbing rather than appearing at 100.
        checkpoint("baseline")

        night = now.replace(hour=1, minute=45, second=0, microsecond=0)
        emit("login_success", "LOGIN_SUCCESS", city="Dubai", country="AE",
             device=rogue_device, occurred_at=night)
        checkpoint("reconnaissance")

        # Mass enumeration
        for index, customer in enumerate(customers[: volumes["customerCount"]]):
            emit("customer_profile_view", "CUSTOMER_VIEW", customer=customer,
                 city="Dubai", country="AE", device=rogue_device,
                 occurred_at=night + timedelta(seconds=25 * index))
        checkpoint("enumeration")

        # Sensitive collection
        for index, resource in enumerate(resources[:7]):
            emit("document_download", "DOCUMENT_DOWNLOAD", resource=resource,
                 city="Dubai", country="AE", device=rogue_device,
                 occurred_at=night + timedelta(minutes=1, seconds=20 * index))
        checkpoint("collection")

        # Exfiltration
        target = resources[0] if resources else None
        emit("sensitive_file_transfer", "SENSITIVE_FILE_TRANSFER", resource=target,
             device_label=USB_MEDIA, city="Dubai", country="AE", severity="CRITICAL",
             metadata={
                 "fileName": target.file_name if target else "customer_pii_export.csv",
                 "fileSize": target.file_size if target else 18_400_000,
                 "classification": target.classification if target else "RESTRICTED",
             },
             occurred_at=now - timedelta(minutes=3))
        checkpoint("exfiltration")

    # Scenarios written as acts already scored their final state; the rest are
    # scored once here. Either way `last_result` holds the verdict.
    if last_result is None:
        checkpoint(key)

    result = last_result
    assessment = result["assessment"]

    return {
        "scenario": key,
        "description": SCENARIOS[key],
        "employee": {
            "id": str(employee.id),
            "name": employee.name,
            "email": employee.email,
            "employeeCode": employee.employee_code,
        },
        "risk": assessment.to_dict(),
        "alert": result["alert"].to_dict() if result["alert"] else None,
        "ml": result["ml"].to_dict(),
        "baselineDeviation": result["baselineDeviation"],
        "eventsConsidered": result["eventsConsidered"],
        "progression": progression,
        "warnings": warnings,
        "reset": reset_info,
    }
