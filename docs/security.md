# Security

This document covers what Sentinel protects, how, and — as importantly — what it
deliberately does not collect. A monitoring system's safety properties are part
of its design, not a disclaimer attached to it.

## Threat model

Sentinel is a *defensive* system. Its subject is the authorised insider: someone
with valid credentials, legitimate access, and a reason to misuse both. That
shapes everything below, because the adversary is not trying to break in — they
are already in, and their activity looks like work.

**In scope**

| Threat | Detection |
| --- | --- |
| Bulk data collection before leaving | RULE-005, RULE-008 |
| Exfiltration to removable media | RULE-009 |
| Access from unfamiliar locations or devices | RULE-001, RULE-003, RULE-010 |
| Out-of-hours access to sensitive material | RULE-007 |
| Credential sharing / stolen session | RULE-010, RULE-003 |
| Slow drift across the boundary of a role | RULE-011 + baseline deviation |

**Out of scope** — stated so the boundary is explicit rather than assumed: host
compromise, malware, network intrusion, and perimeter defence. Sentinel watches
what authenticated employees do *through the application*, which is why it is a
UEBA system and not a SIEM.

The system also assumes it is not the adversary. Rules 10–12 of the spec are
constraints on *Sentinel*, and they are met structurally rather than by policy —
see "What is deliberately not collected".

## Authentication

JWT (HS256) signed with `JWT_SECRET`, verified on every request. Passwords are
bcrypt via passlib; the plaintext never reaches a log, a database column, or an
event.

### The token carries no authority

```python
user_id = payload.get("sub")        # the only claim read
user = db.query(User).filter(User.id == uuid_mod.UUID(str(user_id))).first()
```

`get_current_user` resolves `sub` to a user and loads their roles from
`user_roles` on **every request**. The token's `role` claim is never consulted.
Two consequences:

- **Forging a claim grants nothing.** A hand-crafted token with
  `{"role": "ADMIN"}` authenticates as whoever `sub` names and no more. Covered
  by `test_a_forged_role_claim_does_not_grant_admin`.
- **Revocation is immediate.** Removing a role or setting `status != "ACTIVE"`
  takes effect on the next request rather than when the token expires. An
  `INACTIVE` account is refused with 403 even holding a valid, unexpired token.

Access tokens expire in `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30); refresh
tokens in `REFRESH_TOKEN_EXPIRE_DAYS`. `decode_token` enforces
`type == "access"`, so a refresh token cannot be presented as an access token.

### Authentication events are recorded

Every successful login writes an `EMPLOYEE_ACTION` login event; every failed
login writes a `LOGIN_FAILURE` carrying `{"reason": "bad_password"}` — a *value*,
never the attempted credential, and never the stored hash. Logout writes
`LOGOUT`. A test asserts that no submitted password, correct or incorrect, is
persisted anywhere in the event row.

## Authorisation

Three role groups, defined once in `app/core/dependencies.py` and imported
everywhere:

| Group | Roles | Portal |
| --- | --- | --- |
| `EMPLOYEE_ROLES` | TELLER, RELATIONSHIP_MANAGER, BRANCH_MANAGER, COMPLIANCE_OFFICER, OPERATIONS_MANAGER | Employee banking portal |
| `ADMIN_ROLES` | ADMIN, SECURITY_MANAGER, SECURITY_ANALYST | Security console (read and write) |
| `VIEWER_ROLES` | VIEWER | Security console (read only) |

The three groups are **pairwise disjoint**, asserted by
`test_the_two_role_groups_are_disjoint`. That is what makes the following two
statements true rather than aspirational.

### Employees cannot reach the console

Every security route is guarded; none relies on the frontend to hide a link.
`tests/test_console_access.py` asserts that a TELLER receives 403 from every
console route, read or write.

### The security team cannot act as employees

`require_bank_staff` admits `BANKING_ROLES` only. Platform roles —
including ADMIN — are excluded. This is separation of duties, and it cuts
against the obvious convenience: an administrator who could browse the customer
book through the employee router would be reading customer records under the
employee portal's telemetry, which is precisely the access pattern this system
exists to make visible. The security team investigates employee access through
`/api/v1/admin/*`; it does not perform it.

Both directions are covered in `tests/test_employee_boundary.py`, which asserts
every employee route refuses an ADMIN *and* a SECURITY_ANALYST, and every admin
route refuses a TELLER.

### Read-only means read-only

In the console, the split is by HTTP verb rather than by role:

- `require_security_read` — `ADMIN_ROLES | VIEWER_ROLES` — guards **GET only**:
  the dashboard, the employee roster and detail, the threat timeline, audit
  logs, the alert queue and case files, the demo scenario list, and ML status.
- `require_security_analyst` — `ADMIN_ROLES` — guards every state change:
  resolving an alert, adding a note, starting an investigation, clearing carried
  risk, recomputing a baseline, and running demo scenarios or history.

`tests/test_console_access.py` asserts that a VIEWER is admitted to all eight
read routes and refused by every write route, and that an analyst still reaches
all eight — so the read-only guard cannot silently narrow the analyst's own
access.

Reading a case file is itself audited (`VIEW_ALERT`), so a VIEWER's access to
employee data is recorded like anyone else's.

## Append-only guarantees

Nothing in the application issues `UPDATE` or `DELETE` against `activities`,
`audit_logs` or `risk_scores`. This is enforced by construction, not by
convention:

- `AuditLog` has **no `updated_at` column**, so "was this edited?" is
  unanswerable rather than merely unanswered.
- No ORM relationship points back into `audit_logs`.
- There is no write route for the audit trail — the API exposes read-only
  endpoints, and entries are appended by the services that perform the audited
  action, in the same transaction as the action itself.
- `reset_risk` clears *carried* risk by **appending** a zero-score row and an
  audit note. It never deletes the scores, alerts or events that came before.

The one `.delete()` in the codebase is against the `user_roles` association
table, which is role *assignment* — not a security event, and not evidence.

Verified by grep: no `delete()` call targets `activities`, `audit_logs` or
`risk_scores`.

## What is deliberately not collected

Spec rules 10–12 constrain the system itself. These are design properties:

| Constraint | How it is met |
| --- | --- |
| *"Never store passwords or secrets inside telemetry."* | `record_event` has no parameter that could carry a credential. Passwords, tokens and API keys have no column in `activities` or `audit_logs`. A test scans event metadata for credential-shaped keys. |
| *"USB activity must be simulated."* | No endpoint surveillance exists or is possible. `usb_events` rows are written only by `POST /api/v1/simulation/usb/*`, which accept a device label from the caller. Nothing enumerates hardware. |
| *"Location monitoring must use approximate/simulated information rather than invasive tracking."* | Events carry `city` and `country` only — no coordinates, no GPS, no IP geolocation lookup. RULE-010 compares *city change within an interval* rather than computing real distance, and marks its evidence `"approximate": True`. |
| *"Synthetic banking data only."* | Customers, accounts, transactions and loans are generated by `app/utils/seed_banking.py`. No real customer information exists in this repository. |
| *"Security events must be append-only."* | See above. |
| *"Never expose stack traces in production."* | A global handler returns `{"error": {"code", "message"}}`; the traceback goes to the log. |
| *"Never expose ML model internals server-side."* | `/api/v1/ml/status` is console-gated. Feature weights, training statistics and the model artefact are never serialised to a client. |
| *"Do not trust client-side role information."* | Roles are resolved from the database per request; the token's `role` claim is ignored. |
| *"Do not implement invasive surveillance."* | There is no keystroke logging, no screen capture, no file-content inspection, no process monitoring, and no agent that runs on an endpoint. The `agent/` ingestion path accepts events an endpoint *reports*; it does not reach in. |

Monitoring is also not visible to its subject: the API does not tell an employee
that a detection pass occurred, and the employee portal exposes only their own
activity (`/api/v1/activity/my`, scoped to the caller with no `user_id`
parameter to override).

## Idempotency and write-time integrity

Demo mode injects synthetic security events under a real employee's identity —
indistinguishable from a genuine incident unless labelled. So every scenario run
appends a `DEMO_SCENARIO_RUN` audit entry naming the operator who triggered it,
and `/api/v1/admin/demo/history` refuses to run twice without `force=true`.

`sync_alert` refreshes an employee's open alert rather than appending a new one
per detection pass, so a sustained anomaly produces one queue entry that gets
worse rather than forty that need triaging.

## Known gaps

Recorded here rather than left implied by silence:

- **No rate limiting (spec §24).** Login, customer search, document download and
  the admin APIs are unthrottled. `require_*` guards enforce *who* may call an
  endpoint; nothing enforces *how often*. Credential-stuffing against
  `/api/v1/auth/login` and scripted enumeration of the customer book are
  therefore bounded only by the rules engine noticing, not by the platform
  refusing.
- **`ml/rules.py`, `ml/risk_engine.py` and `ml/inference.py`** are the original
  detection attempt and remain reachable through `POST /api/v1/ml/predict`.
  They contribute to no alert, but they are live code paths and should be
  consolidated or removed.
- **`app/ml/adapter.py`** contains a `MockAnomalyDetector` that returns random
  results. It is dead code, and random anomaly detection is exactly the wrong
  thing to leave lying around in a security system.

## Reporting

There is no vulnerability disclosure process — this is an academic
demonstration, not a deployed service. The constraints above are what make it
safe to demonstrate: it monitors a simulated bank, with simulated employees,
simulated customers, and simulated removable media.
