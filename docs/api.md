# API Reference

Base URL `/api/v1`. Interactive docs at `/docs` (Swagger) and `/redoc`.

Every endpoint below lists its guard, because in this system the guard is part
of the contract. `🔓` public, `👤` any authenticated user, `🏦` employee
banking role, `👁` security console read-only, `🔒` security console analyst,
`🛡` ADMIN only.

## A note on the endpoint paths

The specification's Phase 21 lists `/api/v1/employee/*` as the employee-portal
prefix. This implementation serves that portal at **`/api/v1/bank/*`** instead.

That is deliberate. `/api/v1/bank/*` already existed, fully working, with its
telemetry wired into the detection pipeline. Adding a second `/api/v1/employee/*`
surface over the same data would have created two code paths for every read —
and the risk that one of them stops emitting telemetry is exactly the failure
this system exists to detect, in the system itself. Duplicating a working
endpoint to satisfy a naming convention trades a real guarantee for a cosmetic
one.

Everything else in Phase 21 is at its specified path: `/api/v1/resources/*`,
`/api/v1/activity/*`, `/api/v1/simulation/usb/*`, `/api/v1/admin/*`.

---

## Health

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| GET | `/health` | 🔓 | Liveness. Process up, database reachable. Deliberately says nothing about the model. |
| GET | `/ready` | 🔓 | Readiness. `database`, `telemetryEvents`, `baselines`, `anomalyModel`. |
| GET | `/` | 🔓 | Service identity. |

`/ready` reports `anomalyModel: "untrained"` without being unready — the rule
engine needs no training, so an untrained model lowers precision, not
availability. Only a missing database makes the service `not_ready`.

Note these are mounted at the **root**, not under `/api/v1`.

---

## Authentication — `/api/v1/auth`

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| GET | `/has-users` | 🔓 | Whether the instance has any accounts (first-run check) |
| POST | `/bootstrap-admin` | 🔓 | Create the first admin; refuses if any user exists |
| POST | `/login` | 🔓 | Returns `accessToken` + user info; writes a login event |
| POST | `/refresh` | 🔓 | Exchange a refresh token for an access token |
| POST | `/logout` | 👤 | Ends the session; writes a `LOGOUT` event |
| GET | `/me` | 👤 | Current user, with roles resolved from the database |

A failed login returns 401 and records `LOGIN_FAILURE` with
`{"reason": "bad_password"}`. Neither the submitted password nor anything
derived from it is persisted.

---

## Employee banking portal — `/api/v1/bank`

Guard `🏦` throughout (`require_bank_staff` — banking roles only; ADMIN and the
security roles are refused). Every meaningful call writes telemetry.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/profile` | The signed-in employee's own portal profile |
| GET | `/branches` · `/branches/{code}` | Branch directory |
| GET | `/customers` | Customer search — emits `CUSTOMER_SEARCH` |
| GET | `/customers/{customer_id}` | Customer detail — emits `CUSTOMER_VIEW` |
| GET | `/accounts/{account_id}` | Account detail — emits `ACCOUNT_VIEW` |
| GET | `/accounts/{account_id}/transactions` | Account ledger — emits `TRANSACTION_VIEW` |
| GET | `/accounts/{account_id}/statement` | Statement view |
| GET | `/transactions` | Transaction search |
| POST | `/transfers` | Money transfer |
| GET · POST | `/loans` | Loan queue / application — `LOAN_VIEW` on read |
| PATCH | `/loans/{loan_id}` | Update a loan application |
| GET | `/kyc` · PATCH `/kyc/{case_number}` | KYC cases |
| GET · POST | `/documents` | Document browser / upload |
| GET | `/notifications` · PATCH `/notifications/{id}/read` · PATCH `/notifications/read-all` | Portal notifications |
| GET · POST | `/support/tickets` | Support tickets |

Access scoping (branch, department, ownership) is applied in the query rather
than after it, so an employee cannot reach another branch's records by editing a
URL.

---

## Sensitive resources — `/api/v1/resources`

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| GET | `` | 👤 | Classified resource registry, filtered to what the caller may reach |
| GET | `/{resource_ref}` | 👤 | Resource detail |
| POST | `/{resource_ref}/access` | 🏦 | Record a `SENSITIVE_DATA_ACCESS` |
| POST | `/{resource_ref}/download` | 🏦 | Record a `DOCUMENT_DOWNLOAD` |

Reads are deliberately open to any authenticated user so the registry is
browsable; the *access* and *download* actions are what require an employee role
and what generate the telemetry. Classification is `PUBLIC` … `RESTRICTED`;
`Resource.allows(roles, department)` is the single access decision.

---

## Activity / telemetry — `/api/v1/activity`

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| GET | `/my` | 👤 | **The caller's own timeline.** Scoped to `current_user.id`. |
| GET | `` | 👁 | The organisation-wide timeline |
| GET | `/{user_id}/user` | 👁 | One employee's timeline |

`/my` takes no `user_id` parameter — there is no argument to tamper with. It is
declared before `/{user_id}/user` so the literal path is not shadowed by the
parameterised one.

---

## USB simulation — `/api/v1/simulation`

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| POST | `/usb/connect` | 🏦 | Simulate plugging in a device |
| POST | `/usb/disconnect` | 🏦 | Simulate removal |
| POST | `/usb/transfer` | 🏦 | Simulate copying a file to removable media |
| GET | `/usb/events` | 👤 | USB history (the caller's own) |

**Simulated only.** No endpoint surveillance exists or is possible: these
endpoints accept a device label from the caller and write a row. Nothing
enumerates hardware. `USB-DEMO-1024` is the demonstrator's convention.

Request bodies use camelCase (`deviceLabel`, `fileName`, `fileSize`,
`resourceRef`).

---

## Security console — `/api/v1/admin`

### Read-only (`👁`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/dashboard` | Cards + charts for the overview (spec §14) |
| GET | `/employees` | Monitored-employee roster, ranked by risk |
| GET | `/employees/{employee_id}` | Full employee-monitoring view (spec §15) |
| GET | `/threats` | Chronological security timeline (spec §16) |
| GET | `/audit-logs` | Append-only audit trail |
| GET | `/alerts` | The alert queue, with status counts |
| GET | `/alerts/{alert_id}` | Full case file — **audits a `VIEW_ALERT`** |
| GET | `/demo/scenarios` | The scripted behaviours available to replay |
| GET | `/ml/status` | Detector status (`/api/v1/ml/status`, same guard) |

### Writes (`🔒`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/alerts/{alert_id}/investigate` | `OPEN` → `INVESTIGATING` |
| POST | `/alerts/{alert_id}/notes` | Append an investigator's note |
| POST | `/alerts/{alert_id}/resolve` | Close with a required reason |
| POST | `/alerts/{alert_id}/false-positive` | Close as a false positive |
| POST | `/employees/{employee_id}/recompute` | Re-run baseline, rules, ML and risk |
| POST | `/employees/{employee_id}/reset-risk` | Clear *carried* risk (appends; deletes nothing) |
| POST | `/demo/scenario/{name}` | Replay one scripted scenario |
| POST | `/demo/history` | Generate 30 days of normal history and train the model |

Every write appends to `audit_logs`. Resolution requires
`resolutionReason` (min 3 chars) — an unexplained closure is not a record an
investigator can defend six months later.

`/demo/history` refuses to run twice without `force=true`, and both demo
endpoints append a `DEMO_SCENARIO_RUN` / `DEMO_HISTORY_GENERATED` entry naming
the operator. Demo mode injects synthetic incidents under a real employee's
identity, which is indistinguishable from a genuine incident unless labelled.

---

## ML — `/api/v1/ml`

| Method | Path | Guard | Purpose |
| --- | --- | --- | --- |
| POST | `/predict` | 🔒 | Score a feature dict with the **legacy** engine |
| GET | `/status` | 👁 | The **live** detector: `loaded`, `modelName`, `trainingRows`, `trainedAt` |

`/predict` drives `ml/inference.py` + `ml/risk_engine.py` + `ml/rules.py` — the
original detection attempt, retained for the ingestion path. It contributes to
no alert. `/status` reports `ml/anomaly.py`, which is what actually scores risk.
Do not read `/predict` as the current model.

---

## Supporting routers

### `/api/v1/users` — staff directory

| Method | Path | Guard |
| --- | --- | --- |
| GET | `/meta/reference`, `/meta/roles` | 👤 |
| GET | `` , `/{user_id}` | `_require_staff_view` — ADMIN, security, branch/ops managers, compliance |
| POST | `` | 🛡 |
| PATCH | `/{user_id}` | 🛡 |
| DELETE | `/{user_id}` | 🛡 |

`DELETE /users/{user_id}` deactivates an account; it does not erase their
activity, alerts or audit history. Deactivation takes effect on the next request
because roles and status are re-resolved from the database.

### `/api/v1/anomalies` — legacy alert surface

| Method | Path | Guard |
| --- | --- | --- |
| GET | `` , `/{anomaly_id}` | 🔒 |
| PATCH | `/{anomaly_id}` | 🔒 |

Superseded by `/api/v1/admin/alerts`, which carries the same rows with the full
lifecycle. Retained for compatibility.

### `/api/v1/investigations`

| Method | Path | Guard |
| --- | --- | --- |
| GET | `` , `/{investigation_id}` | 🔒 |
| POST | `` , `/{id}/assign`, `/{id}/resolve` | 🔒 |
| PATCH | `/{investigation_id}` | 🔒 |
| POST | `/{investigation_id}/assign` | 🔒 (manager) |

### `/api/v1/policies`

| Method | Path | Guard |
| --- | --- | --- |
| GET | `` , `/{policy_id}` | 👤 |
| POST · PUT | `` , `/{policy_id}` | 🔒 manager |
| PATCH | `/{policy_id}/status` | 🔒 manager |
| DELETE | `/{policy_id}` | 🛡 |

`DELETE` here removes a *detection policy* — configuration, not evidence. No
endpoint deletes an activity, an audit entry or a risk score.

### `/api/v1/notifications`

| Method | Path | Guard |
| --- | --- | --- |
| GET | `` | 👤 |
| PATCH | `/{notification_id}/read`, `/read-all` | 👤 |

### `/api/v1/ingestion` and `/api/v1/telemetry`

| Method | Path | Guard |
| --- | --- | --- |
| POST | `/ingestion/activities`, `/ingestion/csv` | 🛡 |
| POST | `/telemetry/browser` | 👤 |
| POST | `/telemetry/agent` | agent key |
| GET | `/telemetry` | 👤 |
| POST · GET · DELETE | `/telemetry/agent-keys` | 🛡 |

`/telemetry/agent` authenticates with an agent API key rather than a user token
— the endpoint an endpoint agent *reports to*. It does not reach into the
endpoint; see `docs/security.md`.

---

## Error format

All errors share one envelope:

```json
{
  "error": {
    "code": "ACCESS_DENIED",
    "message": "Human-readable description"
  }
}
```

Unhandled exceptions return `500` with `code: "INTERNAL_SERVER_ERROR"` and a
generic message; the traceback goes to the server log, never to the client.

| Status | Meaning in this system |
| --- | --- |
| 401 | Missing, malformed or expired token; inactive account |
| 403 | Authenticated but the role does not permit this — including "employee tried to reach the console" and "admin tried to reach the employee portal" |
| 404 | Target not found |
| 409 | Conflicting state, e.g. resolving an already-resolved alert |
| 422 | Request validation failed |

Every response carries `X-Request-ID` and `X-Process-Time`.

## Request examples

```bash
# Log in
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"analyst@sentinel.demo","password":"..."}' | jq -r .accessToken)

# The alert queue, worst first
curl -s "localhost:8000/api/v1/admin/alerts?sort=risk&page_size=10" \
  -H "Authorization: Bearer $TOKEN"

# Replay the combined insider-threat scenario (expect CRITICAL)
curl -s -X POST "localhost:8000/api/v1/admin/demo/scenario/combined_insider" \
  -H "Authorization: Bearer $TOKEN"

# Simulate an employee copying a restricted file to removable media
curl -s -X POST localhost:8000/api/v1/simulation/usb/transfer \
  -H "Authorization: Bearer $TELLER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"deviceLabel":"USB-DEMO-1024","resourceRef":"RES-0007"}'
```
