"""Behavioural baseline tests (spec §8).

The baseline is what makes every other detector personal rather than global, so
its two promises get tested directly:

1. One abnormal day cannot redefine "normal" (bounded adaptation).
2. What counts as habitual decays when it stops happening.

The second is the one that was silently broken: the learned location and device
sets were accumulated into on every recompute, with no bound and no decay, so a
city visited once became permanently "known" — which is precisely the state
RULE-001 exists to notice.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.models.activity import Activity
from app.models.baseline import EmployeeBaseline
from app.models.user import User
from app.services import baseline_service

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


def employee(db, email="baseline.teller@sentinel.in") -> User:
    user = User(
        name="Baseline Teller",
        email=email,
        employee_code="EMP-BASE-01",
        password_hash=hash_password("TestPass123!"),
        department="Branch Ops",
        job_title="Teller",
        branch_name="Vijayawada Central",
        status="ACTIVE",
    )
    db.add(user)
    db.commit()
    return user


def event(user, *, days_ago=0, hours=10.0, city="Vijayawada", event_type="CUSTOMER_SEARCH",
          device="DEVICE-A1024", sensitivity="INTERNAL", customer_id=None, resource_id=None):
    when = (NOW - timedelta(days=days_ago)).replace(
        hour=int(hours), minute=int((hours % 1) * 60), second=0, microsecond=0
    )
    return Activity(
        user_id=user.id,
        timestamp=when,
        event_type=event_type,
        action=event_type.lower(),
        city=city,
        country="IN",
        location=city,
        device=device,
        sensitivity=sensitivity,
        severity="LOW",
        customer_id=customer_id,
        resource_id=resource_id,
    )


def observations(**overrides) -> dict:
    base = {
        "avg_daily_accesses": 40.0,
        "avg_sensitive_accesses": 2.0,
        "avg_downloads": 3.0,
        "avg_customer_searches": 20.0,
        "avg_unique_customers": 15.0,
        "avg_unique_resources": 4.0,
        "locations": {"Vijayawada": 40},
        "countries": {"IN": 40},
        "devices": {"DEVICE-A1024": 40},
        "days": 1,
        "events": 40,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Promise 1 — slow adaptation
# ---------------------------------------------------------------------------

def test_one_extreme_day_moves_a_mean_by_at_most_a_quarter():
    baseline = EmployeeBaseline(avg_daily_accesses=40.0, avg_unique_customers=15.0)

    baseline.update_from_observations(observations(avg_daily_accesses=400.0, avg_unique_customers=200.0))

    # 40 → 400 would be the naive overwrite. The blend moves it to 130.
    assert baseline.avg_daily_accesses == pytest.approx(40.0 * 0.75 + 400.0 * 0.25)
    assert baseline.avg_daily_accesses < 400.0
    assert baseline.avg_unique_customers < 200.0


def test_repeated_extreme_days_are_needed_to_move_a_mean_far():
    baseline = EmployeeBaseline(avg_daily_accesses=40.0)
    for _ in range(10):
        baseline.update_from_observations(observations(avg_daily_accesses=400.0))
    # Ten consecutive days still will not fully adopt the extreme value.
    assert baseline.avg_daily_accesses < 400.0
    assert baseline.avg_daily_accesses > 130.0


def test_adaptation_weight_is_clamped():
    baseline = EmployeeBaseline(avg_daily_accesses=40.0)
    baseline.update_from_observations(observations(avg_daily_accesses=400.0), max_adaptation=5.0)
    assert baseline.avg_daily_accesses == pytest.approx(400.0)


def test_a_missing_observation_leaves_the_mean_alone():
    """A day with no logins must not drag the usual login hour toward zero."""
    baseline = EmployeeBaseline(avg_login_hour=9.5)
    baseline.update_from_observations(observations(avg_login_hour=None))
    assert baseline.avg_login_hour == 9.5


def test_empty_observations_change_nothing():
    baseline = EmployeeBaseline(avg_daily_accesses=40.0, observed_days=7)
    baseline.update_from_observations({})
    assert baseline.avg_daily_accesses == 40.0
    assert baseline.observed_days == 7


# ---------------------------------------------------------------------------
# Promise 2 — habitual sets decay (the regression)
# ---------------------------------------------------------------------------

def test_incremental_update_accumulates_counts():
    baseline = EmployeeBaseline(normal_locations={})
    baseline.update_from_observations(observations(locations={"Vijayawada": 40}))
    baseline.update_from_observations(observations(locations={"Vijayawada": 40}))
    assert baseline.normal_locations["Vijayawada"] == 80


def test_rebasing_replaces_the_sets_instead_of_accumulating():
    """Regression: repeated recomputes inflated counts without bound."""
    baseline = EmployeeBaseline(normal_locations={"Vijayawada": 40})
    baseline.update_from_observations(
        observations(locations={"Vijayawada": 40}), replace_sets=True
    )
    baseline.update_from_observations(
        observations(locations={"Vijayawada": 40}), replace_sets=True
    )
    assert baseline.normal_locations == {"Vijayawada": 40}


def test_a_location_that_stops_appearing_stops_being_normal():
    """The property the accumulation bug destroyed."""
    baseline = EmployeeBaseline(normal_locations={})
    baseline.update_from_observations(
        observations(locations={"Vijayawada": 40, "Dubai": 1}), replace_sets=True
    )
    assert baseline.is_known_location("Dubai") is True

    # The next window contains no activity from Dubai at all.
    baseline.update_from_observations(
        observations(locations={"Vijayawada": 40}), replace_sets=True
    )
    assert baseline.is_known_location("Dubai") is False


def test_rebasing_clears_a_set_the_window_no_longer_mentions():
    baseline = EmployeeBaseline(normal_devices={"DEVICE-OLD": 30})
    baseline.update_from_observations(
        observations(devices={"DEVICE-A1024": 40}), replace_sets=True
    )
    assert baseline.normal_devices == {"DEVICE-A1024": 40}
    assert baseline.is_known_device("DEVICE-OLD") is False


def test_recompute_baseline_rebases_rather_than_accumulates(db_session):
    """End-to-end version of the same regression, through the service."""
    user = employee(db_session)
    for day in range(5):
        db_session.add(event(user, days_ago=day))
    db_session.commit()

    baseline_service.recompute_baseline(db_session, user)
    first = dict(baseline_service.get_or_create_baseline(db_session, user).normal_locations)

    baseline_service.recompute_baseline(db_session, user)
    second = dict(baseline_service.get_or_create_baseline(db_session, user).normal_locations)

    assert first == second == {"Vijayawada": 5}


# ---------------------------------------------------------------------------
# Learning from telemetry
# ---------------------------------------------------------------------------

def test_history_becomes_the_expected_means(db_session):
    user = employee(db_session)
    for day in range(4):
        db_session.add(event(user, days_ago=day, event_type="LOGIN_SUCCESS", hours=9.5, city="Vijayawada"))
        for _ in range(3):
            db_session.add(event(user, days_ago=day, hours=11.0))
    db_session.commit()

    baseline = baseline_service.recompute_baseline(db_session, user)

    assert baseline.avg_daily_accesses == pytest.approx(4.0)
    assert baseline.avg_customer_searches == pytest.approx(3.0)
    assert baseline.avg_login_hour == pytest.approx(9.5, abs=0.05)
    assert baseline.observed_days == 4
    assert baseline.sample_events == 16


def test_removable_media_is_not_learned_as_a_workstation(db_session):
    """Regression: USB-DEMO-1024 in `normal_devices` would disarm RULE-003/009."""
    user = employee(db_session)
    db_session.add(event(user, days_ago=1, device="DEVICE-A1024"))
    db_session.add(event(user, days_ago=1, event_type="SENSITIVE_FILE_TRANSFER",
                        device="USB-DEMO-1024", sensitivity="RESTRICTED"))
    db_session.add(event(user, days_ago=1, event_type="USB_CONNECTED", device="USB-DEMO-1024"))
    db_session.commit()

    baseline = baseline_service.recompute_baseline(db_session, user)

    assert baseline.is_known_device("DEVICE-A1024") is True
    assert baseline.is_known_device("USB-DEMO-1024") is False


def test_the_working_window_is_bounded():
    """An odd week must not be able to declare a night shift normal."""
    start, end = baseline_service.working_window([9.0] * 10)
    assert end - start >= baseline_service.MIN_WORK_WINDOW_HOURS

    start, end = baseline_service.working_window([3.0])
    assert end - start <= baseline_service.MAX_WORK_WINDOW_HOURS

    # No history at all falls back to a standard office day rather than 0–0.
    assert baseline_service.working_window([]) == (9.0, 18.0)


# ---------------------------------------------------------------------------
# Deviation scoring
# ---------------------------------------------------------------------------

def test_deviation_is_zero_for_a_cold_start(db_session):
    """Reporting a deviation with nothing to compare against would invent it."""
    user = employee(db_session)
    score, components = baseline_service.baseline_deviation(
        db_session, user, window_start=NOW - timedelta(hours=24), window_end=NOW
    )
    assert score == 0.0
    assert components.get("cold_start") is True


def give_known_history(db, user, *, accesses=10.0, searches=10.0):
    """A baseline that already knows this employee's patch.

    The location sets matter even in a deviation test: an employee whose
    baseline knows no locations at all is "seen somewhere new" on every single
    day, and the +45 penalty would mask whatever the test meant to measure.
    """
    baseline = baseline_service.get_or_create_baseline(db, user)
    baseline.avg_daily_accesses = accesses
    baseline.avg_customer_searches = searches
    baseline.normal_locations = {"Vijayawada": 50}
    baseline.normal_countries = {"IN": 50}
    baseline.normal_devices = {"DEVICE-A1024": 50}
    baseline.observed_days = 20
    baseline.sample_events = 200
    db.commit()
    return baseline


def test_deviation_is_zero_for_a_typical_day(db_session):
    user = employee(db_session)
    give_known_history(db_session, user)

    for _ in range(10):
        db_session.add(event(user))
    db_session.commit()

    score, _ = baseline_service.baseline_deviation(
        db_session, user, window_start=NOW - timedelta(hours=24), window_end=NOW
    )
    assert score == 0.0


def test_deviation_rises_with_a_burst(db_session):
    user = employee(db_session)
    give_known_history(db_session, user)

    for _ in range(40):
        db_session.add(event(user))
    db_session.commit()

    score, components = baseline_service.baseline_deviation(
        db_session, user, window_start=NOW - timedelta(hours=24), window_end=NOW
    )
    assert score > 0.0
    assert components["searches"] > 0.0


def test_an_unseen_device_adds_a_flat_penalty(db_session):
    """A device is a categorical fact about the employee, not statistical drift."""
    user = employee(db_session)
    give_known_history(db_session, user)

    for _ in range(10):
        db_session.add(event(user, device="DEVICE-STRANGER"))
    db_session.commit()

    score, components = baseline_service.baseline_deviation(
        db_session, user, window_start=NOW - timedelta(hours=24), window_end=NOW
    )
    assert score >= baseline_service.UNSEEN_DEVICE_PENALTY
    assert components["unseenDevices"] == ["DEVICE-STRANGER"]
