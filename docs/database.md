# Database

PostgreSQL in the application; SQLite in the test suite. The schema is written
to be portable between them — the one place that was not (date bucketing in
dashboard trend queries, where `date_trunc` has no SQLite equivalent) is done in
Python instead.

## Migrations

Alembic, four revisions, linear:

| Revision | Adds |
| --- | --- |
| `001_initial_tables` | `users`, `roles`, `user_roles`, `activities`, `anomalies`, `risk_events`, `investigations`, `investigation_events`, `detection_policies`, `notifications`, `telemetry_events`, `user_sessions`, `agent_keys` |
| `002_employee_fields` | `users.employee_code`, department/job-title/branch fields, account status |
| `003_banking_tables` | `branches`, `customers`, `accounts`, `transactions`, `loan_applications`, `kyc_cases`, `portal_documents`, `support_tickets`, `portal_notifications` |
| `004_detection_foundation` | `resources`, `devices`, `usb_events`, `employee_baselines`, `risk_scores`, `audit_logs`, `admin_actions` |

```bash
cd backend
alembic upgrade head          # apply
alembic downgrade -1          # roll back one
alembic revision --autogenerate -m "description"
```

Revision `004` is the one that matters: it adds the tables the detection
pipeline is built on. Revisions `001`–`003` are the pre-existing application,
deliberately evolved rather than replaced.

## The tables that carry the project

### `activities` — security telemetry

The spine. One row per meaningful employee action; everything downstream reads
from it.

| Group | Columns |
| --- | --- |
| Identity | `id`, `user_id` → `users.id`, `timestamp` |
| What | `event_type`, `action`, `resource` (human label) |
| Structured refs | `resource_id` → `resources.id`, `customer_id` → `customers.id`, `device_id` → `devices.id` |
| Context | `source_ip`, `device`, `location`, `country`, `city`, `application` |
| Assessment | `sensitivity`, `severity`, `risk_contribution` |
| Variable | `metadata` (JSON), `created_at` |

There is no `updated_at`. Its absence is intentional and is the mechanism by
which the append-only guarantee is kept — read the model docstring:
*"nothing in the application updates or deletes rows."*

Indexes: `user_id`, `timestamp`, `event_type`, `severity`, `customer_id`,
`resource_id`, `device_id`, and the composite `(user_id, timestamp)` that the
24-hour detection window queries on every scored event.

`event_type` is constrained to `EVENT_TYPES` (spec §6's vocabulary) plus
`INTERNAL_ACTION` for portal operations that are recorded for timeline
completeness but never scored.

**Structured columns over JSON wherever the field is known.** `metadata` carries
only genuinely variable detail — this is spec §6's "structured metadata rather
than arbitrary uncontrolled JSON", applied. Passwords and tokens have no column
and no representation; the recorder has no parameter that could carry one.

### `resources` — classified registry

Every document, report and dataset an employee can reach.

| Column | Purpose |
| --- | --- |
| `resource_id` | Business key, `RES-0001`, unique |
| `name`, `resource_type` | What it is |
| `classification` | `PUBLIC` … `RESTRICTED` — drives access, sensitivity, risk weight |
| `owner`, `owner_department` | Business owner |
| `allowed_roles`, `allowed_departments` | Comma-separated access lists; empty means "any employee" |
| `customer_id` | Set when the resource wraps a customer artefact |
| `file_name`, `file_size`, `mime`, `downloadable` | Presentation attributes |

The classification ladder and its risk weights (§5):

| Classification | Rank | Risk weight | Sensitive? |
| --- | --- | --- | --- |
| `PUBLIC` | 0 | 0.00 | no |
| `INTERNAL` | 1 | 0.05 | no |
| `CONFIDENTIAL` | 2 | 0.15 | **yes** |
| `HIGHLY_CONFIDENTIAL` | 3 | 0.30 | **yes** |
| `RESTRICTED` | 4 | 0.45 | **yes** |

`allows(roles, department)` is the single access decision. An empty allow-list
means the resource is open to any authenticated employee — deliberately *not*
the default, since the requirement is that not every employee can reach
everything. `ADMIN` always passes, and that override is separately audited.

### `employee_baselines` — learned normal

One row per employee (`employee_id` is unique).

| Group | Columns |
| --- | --- |
| Login rhythm | `avg_login_hour`, `login_hour_stddev` |
| Working window | `work_start_hour`, `work_end_hour` |
| Volume means | `avg_daily_accesses`, `avg_sensitive_accesses`, `avg_downloads`, `avg_customer_searches`, `avg_unique_customers`, `avg_unique_resources` |
| Sessions | `typical_session_minutes` |
| Learned sets | `normal_locations`, `normal_countries`, `normal_devices`, `typical_departments` (all JSON: value → count) |
| Provenance | `observed_days`, `sample_events`, `last_computed_at`, `notes` |

Unlike the audit tables, this one *does* have `updated_at` — a baseline is
mutable learned state, not a record of something that happened. Overwriting it
destroys no evidence.

The learned sets are **rebased** from the rolling 30-day window on each
recompute rather than accumulated. See `docs/architecture.md` for why: counts
have no bounded step size, so accumulation made them monotonically expanding and
a once-visited city stayed "normal" forever.

### `risk_scores` — assessment history

One row per scoring run, not one row per employee. Keeping history is what lets
the console draw a trend and show what changed between two assessments.

| Column | Purpose |
| --- | --- |
| `current_score`, `previous_score`, `change` | The value and its movement |
| `risk_level` | `LOW` … `CRITICAL` |
| `rule_score`, `ml_score`, `baseline_score` | Component subtotals, so the UI can show "rules 45 · ML 22 · baseline 14" |
| `reasons` | JSON list of `{source, code, label, contribution}` — the explainability payload |
| `window_start`, `window_end` | What period this summarises |
| `note` | Operator note (e.g. the reset marker) |

Bands (§11) live in `RISK_BANDS` and are evaluated high → low, so `level_for_score`
is a single ordered scan:

```
81–100 CRITICAL   61–80 HIGH   41–60 ELEVATED   21–40 MODERATE   0–20 LOW
```

### `audit_logs` — append-only

| Group | Columns |
| --- | --- |
| Actor | `actor_id`, `actor_code` (snapshot — survives a rename), `actor_type` (`EMPLOYEE`/`ADMIN`/`SYSTEM`) |
| Action | `action`, `target_type`, `target_id`, `description` |
| Provenance | `ip_address`, `request_id`, `user_agent` |
| Payload | `details` (JSON) |
| | `created_at` — and nothing else |

No `updated_at` column. No ORM relationship pointing back into the table.
No write endpoint in the API — the routes are read-only, and there is
deliberately no route that creates an audit entry directly; entries are appended
by the services that perform the audited action, in the same transaction.

`actor_code` is a snapshot rather than a join because an audit entry must still
be readable after the actor's record changes. `actor_id` is nullable so
`actor_type=SYSTEM` can represent automated detections.

Action vocabulary: authentication (`LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`),
employee activity (`EMPLOYEE_ACTION`, `SENSITIVE_ACCESS`, `DOCUMENT_DOWNLOAD`,
`USB_EVENT`), alert lifecycle (`VIEW_ALERT`, `START_INVESTIGATION`, `ADD_NOTE`,
`RESOLVE_ALERT`, `MARK_FALSE_POSITIVE`), detection (`RISK_CHANGE`,
`ALERT_CREATED`, `RESET_RISK`), and administration (`USER_CREATED`,
`USER_UPDATED`, `ROLE_CHANGED`, `DEMO_SCENARIO_RUN`, `DEMO_HISTORY_GENERATED`).

The last two exist because demo mode injects synthetic security events under a
real employee's identity. That is indistinguishable from a genuine incident
unless it is labelled, so every scenario run appends an entry naming the
operator who triggered it.

### `anomalies` — the alert queue

Pre-existing table, extended. Statuses are `OPEN`, `INVESTIGATING`, `RESOLVED`,
`FALSE_POSITIVE`; `ACTIVE_ALERT_STATUSES = ["OPEN", "INVESTIGATING"]` is the
module constant every query filters on, so "active" has one definition.
`normalised_status` maps legacy values (`IN_REVIEW`, `ESCALATED`) forward on
read rather than requiring a data migration.

One alert per incident: `sync_alert` refreshes the open alert for an employee
instead of appending a new one per detection pass.

### `devices`, `usb_events`, `admin_actions`

- **`devices`** — `device_id` (`DEVICE-A1024`), `fingerprint`, browser, OS,
  `first_seen`, `last_seen`, `seen_count`, `is_trusted`, `is_new`. A device
  becomes trusted by being seen before; `is_new` drives the new-device rule.
- **`usb_events`** — simulated removable-media activity. `device_label`
  (`USB-DEMO-1024`), `action` (`CONNECT`/`DISCONNECT`/`TRANSFER`), `file_name`,
  `file_size`, `classification`, `resource_id`. No endpoint surveillance exists
  or is possible; these rows are written only by the simulation endpoints.
- **`admin_actions`** — the investigation workflow's own record: `alert_id`,
  `action`, `note`, `previous_status`, `new_status`. Complements `audit_logs`:
  the audit log is the security trail, `admin_actions` is the case history.

## Indexing

Indexes exist for the columns the pipeline actually filters on, which is the
list spec §2 names:

| Table | Indexed |
| --- | --- |
| `activities` | `user_id`, `timestamp`, `event_type`, `severity`, `customer_id`, `resource_id`, `device_id`, `(user_id, timestamp)` |
| `risk_scores` | `employee_id`, `current_score`, `risk_level`, `timestamp`, `(employee_id, timestamp)` |
| `audit_logs` | `actor_id`, `action`, `target_id`, `request_id`, `created_at`, `(actor_id, created_at)`, `(target_type, target_id)` |
| `resources` | `resource_id`, `classification`, `resource_type`, `customer_id`, `created_at` |
| `anomalies` | status, risk score, detected-at |
| `usb_events` | `employee_id`, `device_label`, `action`, `resource_id`, `occurred_at` |
| `devices` | `device_id`, `employee_id`, `fingerprint` |

The composite `(user_id, timestamp)` on `activities` is the one that earns its
keep: the detection window query runs on every scored event.

## Cross-dialect notes

Two deliberate choices keep SQLite and PostgreSQL in agreement:

1. **No `date_trunc`.** The dashboard's 14-day trend loops in Python, bucketing
   in the application. `func.date()` behaves differently on the two backends,
   and a test that passes on SQLite while the app silently misreports on
   PostgreSQL is worse than a slightly slower loop.
2. **`postgresql.UUID(as_uuid=True)`** is used throughout. SQLAlchemy maps it to
   `CHAR(32)` on SQLite without the application needing to care.

Timestamps are timezone-aware everywhere (`DateTime(timezone=True)` plus
`datetime.now(timezone.utc)` defaults). Naive datetimes are the usual source of
"the after-hours rule fires at 3pm" bugs, so the rule engine and feature
extractor both normalise through an `_aware()` helper before comparing.

## Legacy tables

`telemetry_events`, `risk_events`, `agent_keys` and `user_sessions` predate the
detection foundation. They are retained rather than dropped — `risk_events`
still feeds the dashboard's behaviour-drift panel, and `telemetry_events` backs
the agent ingestion path. `activities` is the table the detection pipeline uses;
treat `telemetry_events` as a separate ingestion stream, not a duplicate.

Likewise `ml/rules.py` (8 rules), `ml/risk_engine.py` and `ml/inference.py` are
the original detection attempt, still reachable through `/api/v1/ml/predict`.
The live pipeline is `ml/rule_engine.py` (11 rules) + `ml/anomaly.py` +
`app/services/risk.py`. See `docs/ml.md` for the distinction — it matters,
because `/api/v1/ml/status` reports the live detector and not the stub.
