# Architecture

## The one-sentence version

An employee does something in a banking portal; the action is written down as an
event; that event is compared against what is normal *for that person* and
against eleven deterministic rules; the comparison becomes a number between 0
and 100; a number above 41 becomes an alert an analyst can investigate.

Everything else in this document is about making that sentence true without
lying, without surveilling anyone, and without letting a statistical model
decide someone is a criminal on its own.

## Component map

```
                    ┌─────────────────────────────────────────┐
   Employee ───────▶│  /api/v1/bank/*  (banking routers)      │
   (TELLER, RM,     │  customers, accounts, transactions,     │
    BRANCH_MANAGER…) │  loans, documents, KYC                  │
                    └───────────────┬─────────────────────────┘
                                    │ every meaningful read/write
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │  services/telemetry.py                  │
                    │  record_event(...) — the single funnel  │
                    └───────────────┬─────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌───────────────┐   ┌──────────────────┐   ┌────────────────┐
      │  activities   │   │  devices,        │   │  audit_logs    │
      │  (append-only)│   │  usb_events,     │   │  (append-only) │
      │               │   │  user_sessions   │   │                │
      └───────┬───────┘   └──────────────────┘   └────────────────┘
              │
              │  on scored event types only
              ▼
    ┌───────────────────────────────────────────────────────────────┐
    │  services/detection.py :: evaluate_employee()                 │
    │                                                               │
    │   1. collect_window()      24h of this employee's events      │
    │   2. extract_features()    15-dim behavioural vector          │
    │   3. ml/rule_engine        11 rules → RuleHit[]               │
    │   4. ml/anomaly            Isolation Forest → 0–100           │
    │   5. baseline deviation    how far from their own normal      │
    │   6. services/risk         combine → 0–100 + reasons          │
    │   7. sync_alert            ≥41 → one alert per incident       │
    └───────────────────────────────┬───────────────────────────────┘
                                    ▼
                    ┌─────────────────────────────────────────┐
                    │  /api/v1/admin/*  (security console)    │
                    │  Analyst investigates; every action is  │
                    │  itself appended to audit_logs          │
                    └─────────────────────────────────────────┘
```

## Why the detection stack is shaped this way

### 1. Telemetry has exactly one entry point

Every recorded event goes through `services/telemetry.py :: record_event`. There
is no second path that writes to `activities`, and the function's signature has
no parameter that could carry a credential — no `password`, no `token`, no
`metadata` blob that a caller could stuff one into. Sensitive-data events are
additionally mirrored into `audit_logs` so that resource access survives even if
telemetry retention is later trimmed.

This is a structural answer to "never store passwords or tokens in activity
logs": the recorder *cannot* be handed one. A test asserts a failed login
persists the reason and nothing else.

### 2. The rule score is the base; statistics are corroboration

The risk engine combines three signals, but not as a weighted average. A
weighted average has a quiet failure mode: when a component is missing, the
remaining weights renormalise and the *achievable maximum falls*. With no ML
model trained — which is every fresh install — a 0.5/0.3/0.2 blend caps the score
at 71/100. The CRITICAL band becomes unreachable by construction, and the
specification's most serious scenario silently cannot fire.

So the rule score is the **base**, and the other signals fill the headroom above
it:

```
risk = rule_score + (100 − rule_score) × corroboration × 0.50
```

Three consequences worth naming:

- A missing signal lowers nothing, because corroboration only ever adds.
- Statistics alone can never exceed the ELEVATED band. Being unusual is not the
  same as being malicious, and the model is not trusted to make that leap.
- A rule that reports CRITICAL floors the composite at 61 (HIGH), and a HIGH
  rule floors it at 41 — the alert threshold. A rule's severity is a claim about
  the behaviour it names, and the composite must not contradict it: a USB
  exfiltration cannot be filed as a middle-severity non-event because the
  employee happens to be statistically unremarkable that day.

The floor reads the *set* of distinct rules that fired, never their count, so
repeating one behaviour cannot inflate the score. That is the same invariant
that keeps repeated identical events from climbing indefinitely.

### 3. Alerts are incidents, not events

`sync_alert` refreshes the open alert for an employee rather than appending a new
one per detection pass. A sustained anomaly produces one queue entry that gets
worse, not forty that need triaging. The alert is closed when the score falls
back below threshold, and both the creation and the closure are audited.

### 4. Events are append-only, including the analyst's own actions

Nothing in the application issues an `UPDATE` or `DELETE` against `activities`,
`audit_logs` or `risk_scores`. `AuditLog` has no `updated_at` column by design —
its absence is the guarantee. When an analyst resolves an alert or marks it a
false positive, that appends a new row; the original detection is still there.
`reset_risk` clears *carried* risk so an employee is not permanently marked, and
it does so by appending a risk row of zero and a note, never by erasing history.

### 5. Role comes from the database, never the token

`get_current_user` parses the token's `sub` claim to find *who* is calling, then
loads that user and their roles from the database. The token's `role` claim is
ignored. A forged claim therefore grants nothing, and revoking a role takes
effect immediately rather than when the token happens to expire.

### 6. The two portals are disjoint in both directions

Banking roles (TELLER, RELATIONSHIP_MANAGER, BRANCH_MANAGER, COMPLIANCE_OFFICER,
OPERATIONS_MANAGER) may use the employee portal and not the security console.
Platform roles (ADMIN, SECURITY_MANAGER, SECURITY_ANALYST, VIEWER) may use the
security console and not the employee portal.

The second half is the less obvious one and the more important. Letting an
administrator browse the customer book through the employee router would mean an
analyst reading customer records under the employee portal's telemetry — which is
precisely the access pattern this system exists to make visible. Separation of
duties means the security team investigates employee access through
`/api/v1/admin/*`; it does not perform it. Both directions are asserted in
`tests/test_employee_boundary.py`.

## The request lifecycle

Taking a single real example — a teller opens a customer's account page:

1. **Auth.** `HTTPBearer` extracts the token; `get_current_user` validates the
   signature, reads `sub`, loads the `User` and resolves roles from `user_roles`.
2. **Authorisation.** `require_bank_staff` checks the resolved roles against
   `BANKING_ROLES`. An admin session stops here with 403.
3. **Business logic.** The customer and account are loaded. Ownership and
   department scoping are applied in the query, not after it — an employee
   cannot reach another branch's records by editing a URL.
4. **Telemetry.** `record_event` writes an `ACCOUNT_VIEW` row carrying the
   employee, resource, customer, device, timestamp, approximate city/country,
   and a structured `metadata` dict.
5. **Detection.** `ACCOUNT_VIEW` is in `SCORED_EVENT_TYPES`, so
   `evaluate_employee` runs: window → features → rules → model → baseline →
   risk → alert.
6. **Response.** The caller receives the data. They are not told a detection
   pass occurred; the monitoring is deliberately not visible to its subject.
7. **Observability.** Middleware has already attached `X-Request-ID` and
   `X-Process-Time`, and logged the method, path, status and latency.

Step 5 is the expensive one, which is why `SCORED_EVENT_TYPES` exists: support
tickets and preference changes are still *recorded* (so the timeline is
complete) but do not trigger a scoring pass. Recording and scoring are separate
concerns with separate costs.

> **Not yet implemented: rate limiting (spec §24).** Login, customer search,
> document download and the admin APIs are currently unthrottled. This is a
> known gap, recorded here rather than left implied by silence.

## The behavioural baseline

A bank-wide average is useless — a compliance officer's normal Tuesday looks
like an anomaly for a teller. So every employee gets an `EmployeeBaseline`
derived from their own history:

| Field group | Contents | How it is learned |
| --- | --- | --- |
| Login rhythm | `avg_login_hour`, `login_hour_variance` | Median and MAD of observed login hours |
| Working window | `typical_work_start/end` | Median ± 2σ, clamped to a 6–14h window |
| Locations | `normal_locations` | City → count over a rolling 30-day window |
| Countries | `normal_countries` | Country → count over the same window |
| Devices | `normal_devices` | Device fingerprint → count |
| Volume | `avg_daily_accesses`, `avg_sensitive_accesses`, `avg_downloads`, `avg_customer_searches` | Means over the window |
| Session | `avg_session_duration_minutes` | Mean over the window |

Two design decisions matter:

**Adaptation is bounded.** `update_from_observations` moves a mean at most 25%
of the way toward the new observation. One extreme day cannot redefine someone's
normal — the requirement that an abnormal event must not immediately become the
baseline is enforced numerically, not by convention.

**The learned sets are rebased, not accumulated.** This one was a real bug. The
means are self-limiting because their step size is bounded; counts have no such
bound. Accumulating counts on every recompute made `normal_locations` a set that
only ever grew, so a city visited once stayed "known" forever with a count that
climbed monotonically — the exact opposite of the stated behaviour, and enough
to disarm the unusual-location rule for any employee who had ever travelled.
`recompute_baseline` now passes `replace_sets=True`, so the sets are exactly
what the rolling window contains. A one-off visit ages out.

Robust statistics (median, MAD×1.4826) are used throughout rather than mean and
standard deviation, because a single 400-access day would drag a mean far enough
to hide the next anomaly. MAD is a statement about the middle of a distribution,
which is what "normal" means here.

## Where the ML sits, and where it does not

The Isolation Forest consumes the same 15-dimensional vector the rules reason
about, fits on each employee's own day-by-day history, and emits a calibrated
0–100 score where 50 means "exactly typical".

What it deliberately cannot do:

- **It cannot raise an alert by itself.** Statistics alone top out at ELEVATED.
  A model fitted on unlabelled data can tell you someone is unusual; it cannot
  tell you they are stealing.
- **It cannot lower a score by being absent.** An untrained model contributes
  nothing rather than contributing zero — see the headroom model above.
- **It cannot be reported as a verdict.** `/ready` says `untrained`, not
  `not ready`, because the rule engine needs no training and still works.

Explanations come from per-feature robust z-scores against the saved training
distribution — "downloads were 4.1σ above this employee's typical day" is a
claim the model can actually support. SHAP values over a forest fitted on
unlabelled data would not be more truthful, only more elaborate.

## Failure behaviour

| Failure | What happens |
| --- | --- |
| No trained model | Detection runs on rules + baseline. Score not diluted. |
| No baseline yet | Rules still fire; deviation treats everything as unremarkable. |
| One rule raises | Logged via `logger.exception`, the other ten still run. |
| Database unreachable | `/health` reports `degraded`, `/ready` reports `not_ready`. |
| Unhandled exception | Global handler returns the error envelope, never a stack trace. |
| Scoring pass fails | The telemetry row is already committed; the user's request still succeeds. |

That last row is the important one. Monitoring is a side effect of the request,
not a precondition for it. A detection bug must never be able to break the
banking portal it is watching.
