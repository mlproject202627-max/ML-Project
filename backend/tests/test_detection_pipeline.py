"""End-to-end detection pipeline tests (spec §12, §17, §19, §25).

The workflow these pin down is the one the whole project exists to demonstrate:

    action → telemetry → rules + ML + baseline → risk score → alert

Everything here runs against a real database session, so a break in any seam
between those stages shows up as a failing test rather than a quiet zero.

The clock is pinned. Several rules are functions of the wall-clock hour
(unusual login time, after-hours access), so a suite that reads `now()` passes
or fails depending on when it is run — which is worse than not testing at all.
"""
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.activity import Activity
from app.models.anomaly import Anomaly
from app.models.audit_log import AuditLog
from app.models.baseline import EmployeeBaseline
from app.models.resource import Resource
from app.models.risk_score import RiskScore
from app.models.user import Role, User, user_roles
from app.services import detection
from app.services.telemetry import record_event

#: 12:00 UTC — inside the baseline's 08:00–18:00 working window, so nothing is
#: after-hours by accident.
NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

#: Credential-shaped strings that must never reach a security table.
FORBIDDEN_METADATA_KEYS = {
    "password", "passwordhash", "password_hash", "token", "accesstoken",
    "refresh_token", "refreshtoken", "secret", "jwt", "api_key", "apikey",
}


def employee(db, email="pipeline.teller@sentinel.in", role_name="TELLER") -> User:
    """Create an employee-portal user with the given banking role."""
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.flush()

    user = User(
        name="Pipeline Teller",
        email=email,
        employee_code="EMP-PIPE-01",
        password_hash=hash_password("TestPass123!"),
        department="Branch Ops",
        job_title="Teller",
        branch_name="Vijayawada Central",
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    return user


def resource(db, resource_id="RES-TEST-0001", classification="RESTRICTED") -> Resource:
    row = Resource(
        resource_id=resource_id,
        name="PII bulk export",
        resource_type="COMPLIANCE_REPORT",
        classification=classification,
        owner="Compliance",
        owner_department="Compliance",
        file_name="customer_pii_export.csv",
        file_size=18_400_000,
        downloadable=True,
    )
    db.add(row)
    db.commit()
    return row


def give_baseline(db, user, **overrides) -> EmployeeBaseline:
    """A baseline that already knows this employee's normal behaviour."""
    values = dict(
        normal_locations={"Vijayawada": 200},
        normal_countries={"IN": 200},
        normal_devices={"DEVICE-A1024": 200},
        avg_login_hour=9.5,
        login_hour_stddev=0.75,
        work_start_hour=8.0,
        work_end_hour=18.0,
        avg_daily_accesses=40.0,
        avg_sensitive_accesses=2.0,
        avg_downloads=3.0,
        avg_customer_searches=20.0,
        avg_unique_customers=15.0,
        observed_days=20,
        sample_events=800,
    )
    values.update(overrides)
    baseline = EmployeeBaseline(employee=user, **values)
    db.add(baseline)
    db.commit()
    return baseline


def at(hours_before: float) -> datetime:
    return NOW - timedelta(hours=hours_before)


# ---------------------------------------------------------------------------
# Telemetry recording
# ---------------------------------------------------------------------------

def test_record_event_derives_sensitivity_from_the_resource(db_session):
    user = employee(db_session)
    asset = resource(db_session, classification="RESTRICTED")

    activity = record_event(
        db_session, user=user, action="document_download", event_type="DOCUMENT_DOWNLOAD",
        resource=asset, occurred_at=NOW, run_detection=False,
    )

    assert activity.sensitivity == "RESTRICTED"
    assert activity.event_type == "DOCUMENT_DOWNLOAD"
    assert activity.resource_id == asset.id


def test_sensitive_action_appends_an_audit_entry(db_session):
    user = employee(db_session)
    asset = resource(db_session)

    record_event(db_session, user=user, action="document_download",
                 event_type="DOCUMENT_DOWNLOAD", resource=asset,
                 occurred_at=NOW, run_detection=False)

    audit = db_session.query(AuditLog).filter(AuditLog.actor_id == user.id).all()
    assert len(audit) == 1
    assert audit[0].target_type == "RESOURCE"


def test_ordinary_action_is_not_audited(db_session):
    """Auditing everything would bury the events that matter."""
    user = employee(db_session)
    record_event(db_session, user=user, action="customer_search",
                 event_type="CUSTOMER_SEARCH", occurred_at=NOW, run_detection=False)

    assert db_session.query(AuditLog).filter(AuditLog.actor_id == user.id).count() == 0


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------

def test_no_activity_scores_low_and_raises_no_alert(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)

    result = detection.evaluate_employee(db_session, user, now=NOW)

    assert result["assessment"].score == 0.0
    assert result["assessment"].level == "LOW"
    assert result["alert"] is None


def test_normal_working_day_raises_no_alert(db_session):
    """The single most important assertion in the suite.

    A teller doing an ordinary morning's work must produce an empty alert
    queue. A detector that fires here is unusable regardless of what else it
    catches.
    """
    user = employee(db_session)
    give_baseline(db_session, user)

    record_event(db_session, user=user, action="login_success", event_type="LOGIN_SUCCESS",
                 city="Vijayawada", country="IN", device_label="DEVICE-A1024",
                 occurred_at=at(3), run_detection=False)
    for i in range(8):
        record_event(db_session, user=user, action="customer_search",
                     event_type="CUSTOMER_SEARCH", city="Vijayawada", country="IN",
                     device_label="DEVICE-A1024", occurred_at=at(2.5 - i * 0.1),
                     run_detection=False)

    result = detection.evaluate_employee(db_session, user, now=NOW)

    assert result["assessment"].rule_hits == []
    assert result["assessment"].level == "LOW"
    assert result["alert"] is None


def test_sensitive_usb_transfer_raises_an_alert(db_session):
    """Spec §27 scenario 8 — the headline exfiltration case."""
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    record_event(
        db_session, user=user, action="sensitive_file_transfer",
        event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
        device_label="USB-DEMO-1024", occurred_at=NOW,
        severity="CRITICAL", run_detection=False,
    )

    result = detection.evaluate_employee(db_session, user, now=NOW)
    assessment = result["assessment"]

    assert "RULE-009" in [h.rule_id for h in assessment.rule_hits]
    assert assessment.score >= detection.ALERT_THRESHOLD
    assert result["alert"] is not None
    assert result["alert"].severity in ("HIGH", "CRITICAL")


def test_scoring_persists_a_risk_score_row(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)

    detection.evaluate_employee(db_session, user, now=NOW)

    rows = db_session.query(RiskScore).filter(RiskScore.employee_id == user.id).all()
    assert len(rows) == 1
    assert rows[0].risk_level == "LOW"


# ---------------------------------------------------------------------------
# Alert lifecycle (spec §17 — one incident, one queue entry)
# ---------------------------------------------------------------------------

def test_repeated_scoring_refreshes_the_same_alert(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    for _ in range(3):
        record_event(
            db_session, user=user, action="sensitive_file_transfer",
            event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
            device_label="USB-DEMO-1024", occurred_at=NOW,
            severity="CRITICAL", run_detection=False,
        )
        detection.evaluate_employee(db_session, user, now=NOW)

    alerts = db_session.query(Anomaly).filter(Anomaly.user_id == user.id).all()
    assert len(alerts) == 1, "one incident must read as one queue entry"
    assert alerts[0].status == "OPEN"


def test_alert_creation_is_audited(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    record_event(db_session, user=user, action="sensitive_file_transfer",
                 event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
                 device_label="USB-DEMO-1024", occurred_at=NOW,
                 severity="CRITICAL", run_detection=False)
    detection.evaluate_employee(db_session, user, now=NOW)

    actions = {row.action for row in db_session.query(AuditLog).all()}
    assert "ALERT_CREATED" in actions


# ---------------------------------------------------------------------------
# Operator override (spec §19 — audited, and append-only)
# ---------------------------------------------------------------------------

def test_reset_clears_carried_risk_without_deleting_anything(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    record_event(db_session, user=user, action="sensitive_file_transfer",
                 event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
                 device_label="USB-DEMO-1024", occurred_at=NOW,
                 severity="CRITICAL", run_detection=False)
    detection.evaluate_employee(db_session, user, now=NOW)

    scores_before = db_session.query(RiskScore).filter(RiskScore.employee_id == user.id).count()
    alerts_before = db_session.query(Anomaly).filter(Anomaly.user_id == user.id).count()

    detection.reset_risk(db_session, user, reason="reviewed, no action needed")

    # Nothing removed — the override appends.
    assert db_session.query(RiskScore).filter(RiskScore.employee_id == user.id).count() == scores_before + 1
    assert db_session.query(Anomaly).filter(Anomaly.user_id == user.id).count() == alerts_before


def test_reset_leaves_nothing_for_the_next_assessment_to_inherit(db_session):
    """Clearing the state must actually clear it, or replaying a demo lies."""
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    record_event(db_session, user=user, action="sensitive_file_transfer",
                 event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
                 device_label="USB-DEMO-1024", occurred_at=NOW,
                 severity="CRITICAL", run_detection=False)
    detection.evaluate_employee(db_session, user, now=NOW)

    cleared = detection.reset_risk(db_session, user, reason="false alarm")
    assert cleared["previousScore"] >= detection.ALERT_THRESHOLD
    assert cleared["closedAlert"] is not None

    # A quiet window assessed afterwards — far enough ahead that the transfer
    # has aged out — must read quiet, with nothing carried from before.
    later = NOW + timedelta(days=2)
    result = detection.evaluate_employee(db_session, user, now=later)

    assert result["assessment"].previous_score == 0.0
    assert result["assessment"].score < detection.ALERT_THRESHOLD
    assert result["alert"] is None


def test_reset_closes_the_active_alert_and_audits_it(db_session):
    user = employee(db_session)
    give_baseline(db_session, user)
    asset = resource(db_session)

    record_event(db_session, user=user, action="sensitive_file_transfer",
                 event_type="SENSITIVE_FILE_TRANSFER", resource=asset,
                 device_label="USB-DEMO-1024", occurred_at=NOW,
                 severity="CRITICAL", run_detection=False)
    detection.evaluate_employee(db_session, user, now=NOW)

    detection.reset_risk(db_session, user, reason="false alarm")

    alert = db_session.query(Anomaly).filter(Anomaly.user_id == user.id).first()
    assert alert.status == "RESOLVED"
    assert alert.resolution_reason == "false alarm"
    assert alert.resolved_at is not None

    assert "RESET_RISK" in {row.action for row in db_session.query(AuditLog).all()}


# ---------------------------------------------------------------------------
# Secrets never reach the telemetry or audit tables (spec §2, §6, §23)
# ---------------------------------------------------------------------------

def _security_blob(db) -> str:
    parts = [str(row.to_dict()) for row in db.query(Activity).all()]
    for row in db.query(AuditLog).all():
        parts += [str(row.description), str(row.details)]
    return "\n".join(parts)


def test_no_submitted_credential_is_ever_persisted(client, test_user, db_session):
    """The strongest form of the rule: the password the user *typed* — right or
    wrong — must not survive the request in any security table."""
    correct = "TestPass123!"
    wrong = "WrongPass999!"

    ok = client.post("/api/v1/auth/login",
                     json={"email": test_user.email, "password": correct})
    assert ok.status_code == 200
    access_token = ok.json()["accessToken"]

    bad = client.post("/api/v1/auth/login",
                      json={"email": test_user.email, "password": wrong})
    assert bad.status_code == 401

    db_session.expire_all()
    blob = _security_blob(db_session)

    assert correct not in blob
    assert wrong not in blob
    assert access_token not in blob


def test_no_metadata_key_names_a_credential(client, test_user, db_session):
    """Structured metadata is the loophole secrets would leak through."""
    client.post("/api/v1/auth/login",
                json={"email": test_user.email, "password": "TestPass123!"})

    db_session.expire_all()
    offenders = []
    for row in db_session.query(Activity).all():
        for key in (row.extra_metadata or {}):
            if key.replace("-", "_").lower() in FORBIDDEN_METADATA_KEYS:
                offenders.append((row.event_type, key))
    for row in db_session.query(AuditLog).all():
        for key in (row.details or {}):
            if key.replace("-", "_").lower() in FORBIDDEN_METADATA_KEYS:
                offenders.append((row.action, key))

    assert offenders == []


def test_login_still_works_without_a_trained_model(client, test_user):
    """Detection is best-effort: an absent ML model must not fail the login."""
    response = client.post("/api/v1/auth/login",
                           json={"email": test_user.email, "password": "TestPass123!"})
    assert response.status_code == 200
    assert response.json()["accessToken"]
