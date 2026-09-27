"""Rule engine tests (spec §9).

Each of the eleven rules is exercised on its trigger and on the near-miss that
must stay quiet. The near-miss cases matter more than the positives: a rule that
fires on everything explains nothing.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.activity import Activity
from app.models.baseline import EmployeeBaseline
from ml import rule_engine as rules

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
EMPLOYEE = uuid.uuid4()


def event(
    event_type="CUSTOMER_SEARCH",
    *,
    hours_ago=1.0,
    minutes_ago=None,
    city="Vijayawada",
    country="IN",
    sensitivity="INTERNAL",
    device="DEVICE-A1024",
    customer_id=None,
    resource_id=None,
    resource=None,
    metadata=None,
    severity="LOW",
):
    delta = timedelta(minutes=minutes_ago) if minutes_ago is not None else timedelta(hours=hours_ago)
    return Activity(
        id=uuid.uuid4(),
        user_id=EMPLOYEE,
        timestamp=NOW - delta,
        event_type=event_type,
        action=event_type.lower(),
        resource=resource,
        resource_id=resource_id or (uuid.uuid4() if resource else None),
        customer_id=customer_id,
        device=device,
        city=city,
        country=country,
        location=city,
        sensitivity=sensitivity,
        severity=severity,
        extra_metadata=metadata or {},
    )


def baseline(**overrides) -> EmployeeBaseline:
    """A populated baseline representing a normal Vijayawada teller."""
    values = dict(
        normal_locations={"Vijayawada": 120},
        normal_countries={"IN": 120},
        normal_devices={"DEVICE-A1024": 120},
        avg_login_hour=9.5,
        login_hour_stddev=0.75,
        work_start_hour=8.0,
        work_end_hour=18.0,
        avg_customer_searches=30.0,
        avg_unique_customers=22.0,
    )
    values.update(overrides)
    return EmployeeBaseline(**values)


def context(events, base=None, population=None) -> rules.RuleContext:
    return rules.RuleContext(
        employee_id=str(EMPLOYEE),
        events=events,
        baseline=base,
        window_start=NOW - timedelta(hours=24),
        window_end=NOW,
        now=NOW,
        customer_population=population,
    )


# ---------------------------------------------------------------------------
# RULE-001 unusual location
# ---------------------------------------------------------------------------

def test_rule_001_fires_on_unseen_city():
    hit = rules.rule_001_unusual_location(context([event(city="Dubai", country="AE")], baseline()))
    assert hit is not None
    assert hit.rule_id == "RULE-001"
    assert "Dubai" in hit.explanation


def test_rule_001_quiet_for_known_city():
    assert rules.rule_001_unusual_location(context([event()], baseline())) is None


def test_rule_001_quiet_without_baseline():
    """No baseline means no claim about what is unusual — not a guess."""
    assert rules.rule_001_unusual_location(context([event(city="Dubai")], None)) is None


# ---------------------------------------------------------------------------
# RULE-002 unusual login time
# ---------------------------------------------------------------------------

def test_rule_002_fires_on_night_login():
    # NOW is 12:00, so 10 hours ago is 02:00 — far outside a 09:30 normal start.
    night = event("LOGIN_SUCCESS", hours_ago=10)
    assert night.timestamp.hour == 2
    hit = rules.rule_002_unusual_login_time(context([night], baseline()))
    assert hit is not None
    assert hit.rule_id == "RULE-002"


def test_rule_002_quiet_at_usual_hour():
    hit = rules.rule_002_unusual_login_time(
        context([event("LOGIN_SUCCESS", hours_ago=2.5)], baseline())
    )
    assert hit is None


# ---------------------------------------------------------------------------
# RULE-003 new device
# ---------------------------------------------------------------------------

def test_rule_003_fires_on_new_device_flag():
    flagged = event(device="DEVICE-X9999", metadata={"new_device": True})
    hit = rules.rule_003_new_device(context([flagged], baseline()))
    assert hit is not None
    assert "DEVICE-X9999" in hit.explanation


def test_rule_003_quiet_for_known_device():
    assert rules.rule_003_new_device(context([event()], baseline())) is None


# ---------------------------------------------------------------------------
# RULE-004 excessive searches — baseline-relative
# ---------------------------------------------------------------------------

def test_rule_004_quiet_at_normal_volume():
    """A heavy searcher doing their normal 30 searches is not suspicious."""
    events = [event() for _ in range(30)]
    assert rules.rule_004_excessive_customer_searches(context(events, baseline())) is None


def test_rule_004_fires_far_above_personal_norm():
    """Three times the employee's own norm is the threshold, not a fixed number."""
    events = [event() for _ in range(95)]
    hit = rules.rule_004_excessive_customer_searches(context(events, baseline()))
    assert hit is not None
    assert hit.evidence["threshold"] > 30


def test_rule_004_uses_absolute_floor_without_baseline():
    assert rules.search_burst_threshold(None) == float(rules.SEARCH_BURST_THRESHOLD)
    assert rules.rule_004_excessive_customer_searches(context([event() for _ in range(20)])) is None


# ---------------------------------------------------------------------------
# RULE-005 mass record access — the reachability cap
# ---------------------------------------------------------------------------

def test_rule_005_quiet_at_normal_breadth():
    events = [event("CUSTOMER_VIEW", customer_id=uuid.uuid4()) for _ in range(15)]
    assert rules.rule_005_mass_record_access(context(events, baseline(), population=48)) is None


def test_rule_005_fires_on_wide_sweep():
    events = [event("CUSTOMER_VIEW", customer_id=uuid.uuid4()) for _ in range(40)]
    hit = rules.rule_005_mass_record_access(context(events, baseline(), population=48))
    assert hit is not None
    assert hit.evidence["uniqueCustomers"] == 40


def test_rule_005_threshold_is_capped_to_the_population():
    """Regression: 22/day × 3 = 66 exceeds a 48-record book, so the cap applies.

    Without the cap the rule can never fire for exactly the employees with the
    broadest legitimate access.
    """
    threshold, capped = rules.mass_access_threshold(baseline(), population=48)
    assert capped is True
    assert threshold <= 48
    assert threshold == pytest.approx(48 * rules.POPULATION_CEILING)


def test_rule_005_uncapped_when_population_is_large():
    threshold, capped = rules.mass_access_threshold(baseline(), population=500)
    assert capped is False
    assert threshold == pytest.approx(22.0 * rules.BASELINE_MULTIPLIER)


# ---------------------------------------------------------------------------
# RULE-006 sensitive document download
# ---------------------------------------------------------------------------

def test_rule_006_single_restricted_download_is_enough():
    one = event("DOCUMENT_DOWNLOAD", sensitivity="RESTRICTED", resource="HNW register")
    hit = rules.rule_006_sensitive_document_download(context([one], baseline()))
    assert hit is not None
    assert hit.severity == "CRITICAL"


def test_rule_006_low_tier_needs_volume():
    few = [event("DOCUMENT_DOWNLOAD", sensitivity="CONFIDENTIAL") for _ in range(3)]
    assert rules.rule_006_sensitive_document_download(context(few, baseline())) is None

    many = [event("DOCUMENT_DOWNLOAD", sensitivity="CONFIDENTIAL") for _ in range(6)]
    assert rules.rule_006_sensitive_document_download(context(many, baseline())) is not None


def test_rule_006_quiet_for_internal_downloads():
    events = [event("DOCUMENT_DOWNLOAD", sensitivity="INTERNAL") for _ in range(10)]
    assert rules.rule_006_sensitive_document_download(context(events, baseline())) is None


# ---------------------------------------------------------------------------
# RULE-007 after-hours sensitive access
# ---------------------------------------------------------------------------

def test_rule_007_fires_on_flagged_after_hours_access():
    flagged = event("SENSITIVE_DATA_ACCESS", sensitivity="HIGHLY_CONFIDENTIAL",
                    metadata={"after_hours_sensitive": True})
    hit = rules.rule_007_after_hours_sensitive_access(context([flagged], baseline()))
    assert hit is not None
    assert "outside working hours" in hit.explanation


def test_rule_007_quiet_in_hours():
    assert rules.rule_007_after_hours_sensitive_access(
        context([event("SENSITIVE_DATA_ACCESS", sensitivity="HIGHLY_CONFIDENTIAL")], baseline())
    ) is None


# ---------------------------------------------------------------------------
# RULE-008 rapid sensitive sweep
# ---------------------------------------------------------------------------

def test_rule_008_fires_on_rapid_distinct_sensitive_access():
    events = [
        event("SENSITIVE_DATA_ACCESS", minutes_ago=i * 2,
              sensitivity="HIGHLY_CONFIDENTIAL", resource=f"aml-report-{i}")
        for i in range(6)
    ]
    hit = rules.rule_008_rapid_sensitive_sweep(context(events, baseline()))
    assert hit is not None
    assert hit.evidence["distinctResources"] == 6


def test_rule_008_counts_distinct_resources_not_events():
    """Re-reading the same document six times is not a sweep."""
    events = [
        event("SENSITIVE_DATA_ACCESS", minutes_ago=i * 2,
              sensitivity="HIGHLY_CONFIDENTIAL", resource="aml-report")
        for i in range(6)
    ]
    assert rules.rule_008_rapid_sensitive_sweep(context(events, baseline())) is None


def test_rule_008_quiet_when_spread_out():
    events = [
        event("SENSITIVE_DATA_ACCESS", hours_ago=3 + i,
              sensitivity="HIGHLY_CONFIDENTIAL", resource=f"aml-report-{i}")
        for i in range(6)
    ]
    assert rules.rule_008_rapid_sensitive_sweep(context(events, baseline())) is None


# ---------------------------------------------------------------------------
# RULE-009 simulated USB transfer
# ---------------------------------------------------------------------------

def test_rule_009_fires_on_sensitive_transfer():
    transfer = event("SENSITIVE_FILE_TRANSFER", sensitivity="RESTRICTED",
                     resource="customer_pii_export.csv", device="USB-DEMO-1024",
                     metadata={"fileSize": 18_400_000})
    hit = rules.rule_009_usb_sensitive_transfer(context([transfer], baseline()))
    assert hit is not None
    assert hit.severity == "CRITICAL"
    assert "USB-DEMO-1024" in hit.explanation


def test_rule_009_quiet_for_benign_transfer():
    benign = event("FILE_TRANSFER_SIMULATED", sensitivity="INTERNAL", device="USB-DEMO-1024")
    assert rules.rule_009_usb_sensitive_transfer(context([benign], baseline())) is None


# ---------------------------------------------------------------------------
# RULE-010 impossible travel
# ---------------------------------------------------------------------------

def test_rule_010_fires_on_city_change_within_two_hours():
    first = event("LOGIN_SUCCESS", hours_ago=2, city="Vijayawada")
    second = event("LOGIN_SUCCESS", hours_ago=1, city="Hyderabad")
    hit = rules.rule_010_impossible_travel(context([first, second], baseline()))
    assert hit is not None
    assert hit.evidence["from"] == "Vijayawada"
    assert hit.evidence["to"] == "Hyderabad"


def test_rule_010_quiet_when_same_city():
    first = event("LOGIN_SUCCESS", hours_ago=2)
    second = event("LOGIN_SUCCESS", hours_ago=1)
    assert rules.rule_010_impossible_travel(context([first, second], baseline())) is None


def test_rule_010_quiet_when_enough_time_passed():
    first = event("LOGIN_SUCCESS", hours_ago=20, city="Vijayawada")
    second = event("LOGIN_SUCCESS", hours_ago=1, city="Hyderabad")
    assert rules.rule_010_impossible_travel(context([first, second], baseline())) is None


# ---------------------------------------------------------------------------
# RULE-011 composite
# ---------------------------------------------------------------------------

def test_rule_011_requires_three_distinct_rules():
    two = [
        rules.RuleHit("RULE-001", "a", "HIGH", 14.0, "x"),
        rules.RuleHit("RULE-003", "b", "MEDIUM", 12.0, "y"),
    ]
    assert rules.rule_011_multiple_simultaneous_anomalies(context([], baseline()), two) is None

    three = two + [rules.RuleHit("RULE-007", "c", "HIGH", 22.0, "z")]
    hit = rules.rule_011_multiple_simultaneous_anomalies(context([], baseline()), three)
    assert hit is not None
    assert hit.severity == "CRITICAL"


# ---------------------------------------------------------------------------
# Whole-engine behaviour
# ---------------------------------------------------------------------------

def test_ordinary_day_trips_nothing():
    """The most important test here: normal work must produce no hits at all."""
    events = [
        event("LOGIN_SUCCESS", hours_ago=3),
        *[event(minutes_ago=m) for m in (170, 160, 150, 140, 130)],
        *[event("CUSTOMER_VIEW", minutes_ago=m, customer_id=uuid.uuid4()) for m in (120, 110, 100)],
        event("DOCUMENT_DOWNLOAD", minutes_ago=90, sensitivity="CONFIDENTIAL"),
        event("LOGOUT", minutes_ago=5),
    ]
    assert rules.evaluate_context(context(events, baseline(), population=48)) == []


def test_rule_failure_is_isolated_and_logged(caplog):
    """A rule that raises must not blind the others, and must say so."""
    def exploding(ctx):
        raise RuntimeError("boom")

    original = rules.RULES
    rules.RULES = (exploding, rules.rule_001_unusual_location)
    try:
        hits = rules.evaluate_context(context([event(city="Dubai", country="AE")], baseline()))
    finally:
        rules.RULES = original

    assert [h.rule_id for h in hits] == ["RULE-001"]
    assert "boom" in caplog.text
