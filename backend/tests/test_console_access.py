"""Security-console access control (spec §3, §22).

Covers the boundary between the two portals and, within the security console,
between roles that may act and the read-only role that may only look.

The `VIEWER` half of this file exists because the role was, until recently,
decorative: it was seeded, documented as "Read-only security dashboard access",
and admitted by no guard at all. Every security route checked `ADMIN_ROLES`,
which excludes it, so a VIEWER could authenticate successfully and then reach
nothing whatsoever. A role that cannot do what its description claims is worse
than an absent role, because it reads as a control that is not there.

Two properties are asserted throughout:

- Read-only means read-only. VIEWER may read the console; it may not resolve,
  annotate, recompute or run anything.
- The two portals stay separate. A TELLER reaches no part of the console, in
  either direction of the read/write split.
"""
import uuid

import pytest

# Endpoints that only read. VIEWER is admitted; TELLER is not.
READ_ONLY_CONSOLE_ROUTES = [
    "/api/v1/dashboard",
    "/api/v1/admin/dashboard",
    "/api/v1/admin/employees",
    "/api/v1/admin/threats",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/demo/scenarios",
    "/api/v1/admin/alerts",
    "/api/v1/ml/status",
]

# Endpoints that change state. VIEWER is *not* admitted — it is a read-only
# role, and "read-only" has to mean the writes are refused, not merely unused.
WRITE_CONSOLE_ROUTES = [
    ("POST", "/api/v1/admin/demo/scenario/normal", None),
    ("POST", "/api/v1/admin/demo/history", None),
]

# Alert transitions, which need a target id. The guard runs before the handler,
# so the id need not exist for the 403 to be the thing being tested.
ALERT_WRITES = [
    ("investigate", None),
    ("notes", {"note": "A note from a role that should not be able to write."}),
    ("resolve", {"resolutionReason": "Attempted by a read-only role.", "outcome": "RESOLVED"}),
    ("false-positive", {"resolutionReason": "Attempted by a read-only role.", "outcome": "FALSE_POSITIVE"}),
]


@pytest.mark.parametrize("route", READ_ONLY_CONSOLE_ROUTES)
def test_viewer_can_read_the_security_console(client, viewer_headers, route):
    """VIEWER is admitted to every read-only console surface.

    Asserting `== 200` rather than `!= 403` on purpose: a 404 or a 500 would
    also satisfy a loose inequality, and this test is about the route being
    genuinely usable by the role, not merely not-forbidden.
    """
    response = client.get(route, headers=viewer_headers)
    assert response.status_code == 200, f"{route} → {response.status_code}: {response.text[:200]}"


@pytest.mark.parametrize("route", READ_ONLY_CONSOLE_ROUTES)
def test_employee_cannot_read_the_security_console(client, teller_headers, route):
    """A monitored employee reaches no part of the console (spec §3)."""
    response = client.get(route, headers=teller_headers)
    assert response.status_code == 403, f"{route} → {response.status_code}"


@pytest.mark.parametrize("route", READ_ONLY_CONSOLE_ROUTES)
def test_console_refuses_anonymous_callers(client, route):
    """Route protection is not authentication (spec §22)."""
    assert client.get(route).status_code in (401, 403)


@pytest.mark.parametrize("method,route,body", WRITE_CONSOLE_ROUTES)
def test_viewer_cannot_run_demo_actions(client, viewer_headers, method, route, body):
    """Demo mode injects synthetic incidents under a real employee's identity.

    That is the most powerful write in the system, and a read-only role must
    not be able to trigger it.
    """
    response = client.request(method, route, headers=viewer_headers, json=body)
    assert response.status_code == 403, f"{method} {route} → {response.status_code}"


@pytest.mark.parametrize("action,body", ALERT_WRITES)
def test_viewer_cannot_write_to_an_alert(client, viewer_headers, action, body):
    """Notes, resolutions and escalations are analyst work."""
    alert_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/admin/alerts/{alert_id}/{action}",
        headers=viewer_headers,
        json=body,
    )
    assert response.status_code == 403, f"{action} → {response.status_code}"


@pytest.mark.parametrize("action,body", ALERT_WRITES)
def test_employee_cannot_write_to_an_alert(client, teller_headers, action, body):
    alert_id = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/admin/alerts/{alert_id}/{action}",
        headers=teller_headers,
        json=body,
    )
    assert response.status_code == 403, f"{action} → {response.status_code}"


def test_viewer_cannot_reset_an_employees_risk(client, viewer_headers):
    """Clearing an employee's carried risk is a decision, not a lookup."""
    response = client.post(
        f"/api/v1/admin/employees/{uuid.uuid4()}/reset-risk",
        params={"reason": "Attempted by a read-only role."},
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_viewer_cannot_recompute_an_employees_baseline(client, viewer_headers):
    response = client.post(
        f"/api/v1/admin/employees/{uuid.uuid4()}/recompute",
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_analyst_retains_the_whole_console(client, auth_headers):
    """The read-only guard must not have narrowed the analyst's own access.

    A regression here would be silent — every other test in this file asserts a
    denial, so nothing would notice if `require_security_read` had been applied
    where `require_security_analyst` was meant.
    """
    for route in READ_ONLY_CONSOLE_ROUTES:
        response = client.get(route, headers=auth_headers)
        assert response.status_code == 200, f"{route} → {response.status_code}"


def test_the_two_role_groups_are_disjoint():
    """Separation of duties starts with the role definitions themselves.

    A role appearing in both groups would make "an employee cannot reach the
    console" and "an analyst cannot act as an employee" into contradictions
    rather than controls.
    """
    from app.core.dependencies import ADMIN_ROLES, EMPLOYEE_ROLES, VIEWER_ROLES

    assert not (EMPLOYEE_ROLES & ADMIN_ROLES)
    assert not (EMPLOYEE_ROLES & VIEWER_ROLES)
    assert not (ADMIN_ROLES & VIEWER_ROLES)
