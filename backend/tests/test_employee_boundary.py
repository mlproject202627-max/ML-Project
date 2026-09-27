"""Role and identity boundaries (spec §3, §22, §24).

Two sentences from the specification are the whole point of this module:

    Employees cannot access admin APIs. Admins cannot impersonate employees.

Both directions are tested, because a one-way check is the shape of the
original defect: the employee portal admitted every platform role, so an
administrator could browse the customer book through the *employee* router —
reading real customer records under the access pattern this system exists to
make visible.

Every assertion here is about the server's answer. Route guards in the React
app are a usability affordance; these are the ones that decide.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token, hash_password
from app.models.activity import Activity
from app.models.user import Role, User, user_roles

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)

#: Every route the security console exposes. An employee must be refused by
#: all of them, not merely by the dashboard they would land on first.
ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/dashboard"),
    ("GET", "/api/v1/admin/employees"),
    ("GET", "/api/v1/admin/alerts"),
    ("GET", "/api/v1/admin/audit-logs"),
    ("GET", "/api/v1/admin/threats"),
    ("GET", "/api/v1/admin/demo/scenarios"),
    ("GET", "/api/v1/activity"),
]

#: Routes belonging to the employee banking portal. Paths must exist — a typo
#: here would return 404 without ever running the guard, and the test would
#: pass for the wrong reason.
EMPLOYEE_ROUTES = [
    ("GET", "/api/v1/bank/profile"),
    ("GET", "/api/v1/bank/customers"),
    ("GET", "/api/v1/bank/transactions"),
    ("GET", "/api/v1/bank/documents"),
    ("GET", "/api/v1/bank/loans"),
    ("GET", "/api/v1/bank/kyc"),
]


def make_user(db, *, email: str, role_name: str, name: str = None) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.flush()

    user = User(
        name=name or role_name.title(),
        email=email,
        employee_code=f"EMP-{role_name[:6]}-{uuid.uuid4().hex[:4].upper()}",
        password_hash=hash_password("TestPass123!"),
        department="Branch Ops" if role_name == "TELLER" else "Security",
        job_title=role_name.title(),
        branch_name="Vijayawada Central",
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    return user


def headers_for(user: User, role_name: str) -> dict:
    token = create_access_token(data={"sub": str(user.id), "role": role_name})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def teller(db_session):
    return make_user(db_session, email="b.teller@sentinel.in", role_name="TELLER")


@pytest.fixture
def admin(db_session):
    return make_user(db_session, email="b.admin@sentinel.in", role_name="ADMIN")


@pytest.fixture
def analyst(db_session):
    return make_user(db_session, email="b.analyst@sentinel.in", role_name="SECURITY_ANALYST")


# ---------------------------------------------------------------------------
# Employees cannot reach the security console
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_employee_is_refused_by_every_admin_route(client, db_session, teller, method, path):
    response = client.request(method, path, headers=headers_for(teller, "TELLER"))
    assert response.status_code == 403, f"{method} {path} let a TELLER through"


def test_employee_cannot_reset_another_employees_risk(client, db_session, teller, admin):
    response = client.post(
        f"/api/v1/admin/employees/{admin.id}/reset-risk",
        headers=headers_for(teller, "TELLER"),
    )
    assert response.status_code == 403


def test_employee_cannot_run_the_demo(client, teller):
    response = client.post("/api/v1/admin/demo/history", headers=headers_for(teller, "TELLER"))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Platform roles cannot use the employee portal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", EMPLOYEE_ROUTES)
def test_admin_is_refused_by_the_employee_portal(client, db_session, admin, method, path):
    response = client.request(method, path, headers=headers_for(admin, "ADMIN"))
    assert response.status_code == 403, f"{method} {path} let an ADMIN act as an employee"


@pytest.mark.parametrize("method,path", EMPLOYEE_ROUTES)
def test_analyst_is_refused_by_the_employee_portal(client, db_session, analyst, method, path):
    response = client.request(method, path, headers=headers_for(analyst, "SECURITY_ANALYST"))
    assert response.status_code == 403, f"{method} {path} let an analyst act as an employee"


def test_admin_cannot_simulate_device_activity(client, db_session, admin):
    """The USB simulator writes telemetry. An admin must not author it.

    The body is deliberately well-formed: a 422 from a bad payload would pass a
    loose assertion while proving nothing about the guard.
    """
    response = client.post(
        "/api/v1/simulation/usb/connect",
        headers=headers_for(admin, "ADMIN"),
        json={"deviceLabel": "USB-DEMO-9999"},
    )
    assert response.status_code == 403


def test_teller_can_use_their_own_portal(client, db_session, teller):
    """The boundary must not be so tight that it locks out the employee."""
    response = client.get("/api/v1/bank/profile", headers=headers_for(teller, "TELLER"))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# A token's role claim is not authoritative
# ---------------------------------------------------------------------------

def test_a_forged_role_claim_does_not_grant_admin(client, db_session, teller):
    """Authorisation reads the database, not the token's `role` field.

    Reachable only by someone who can already sign tokens, but it pins the
    design: role is resolved per request from `user_roles`, so revoking a role
    takes effect immediately rather than at token expiry.
    """
    forged = create_access_token(data={"sub": str(teller.id), "role": "ADMIN"})
    response = client.get("/api/v1/admin/dashboard", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 403


def test_requests_without_a_token_are_refused(client):
    assert client.get("/api/v1/admin/dashboard").status_code in (401, 403)
    assert client.get("/api/v1/bank/profile").status_code in (401, 403)
    assert client.get("/api/v1/activity/my").status_code in (401, 403)


# ---------------------------------------------------------------------------
# Identity boundaries — the URL is not a parameter you can edit
# ---------------------------------------------------------------------------

def test_my_activity_is_scoped_to_the_caller(client, db_session, teller):
    """Spec §24: editing a URL must not reveal another employee's activity."""
    other = make_user(db_session, email="b.other@sentinel.in", role_name="TELLER")

    db_session.add(Activity(
        user_id=other.id, timestamp=NOW, event_type="CUSTOMER_SEARCH",
        action="customer_search", resource="OTHER-EMPLOYEE-ONLY",
        sensitivity="INTERNAL", severity="LOW",
    ))
    db_session.add(Activity(
        user_id=teller.id, timestamp=NOW - timedelta(minutes=5),
        event_type="LOGIN_SUCCESS", action="login_success",
        resource="MINE", sensitivity="INTERNAL", severity="LOW",
    ))
    db_session.commit()

    response = client.get("/api/v1/activity/my", headers=headers_for(teller, "TELLER"))
    assert response.status_code == 200

    body = response.json()
    resources = {item["resource"] for item in body["items"]}
    assert "MINE" in resources
    assert "OTHER-EMPLOYEE-ONLY" not in resources
    assert all(item["user_id"] == str(teller.id) for item in body["items"])


def test_my_activity_takes_no_user_id_parameter(client, db_session, teller):
    """A `user_id` query parameter would be the obvious way to break the above,
    so its absence is asserted rather than assumed."""
    other = make_user(db_session, email="b.target@sentinel.in", role_name="TELLER")
    db_session.add(Activity(
        user_id=other.id, timestamp=NOW, event_type="CUSTOMER_VIEW",
        action="customer_view", resource="TARGET-ONLY",
        sensitivity="INTERNAL", severity="LOW",
    ))
    db_session.commit()

    response = client.get(
        f"/api/v1/activity/my?user_id={other.id}",
        headers=headers_for(teller, "TELLER"),
    )
    assert response.status_code == 200
    assert all(item["user_id"] == str(teller.id) for item in response.json()["items"])
