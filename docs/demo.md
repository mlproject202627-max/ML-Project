# Demo Guide

## What this demonstrates

The workflow the project exists to prove:

```
employee does something  →  telemetry  →  baseline + rules + ML
    →  risk score  →  alert  →  analyst investigates  →  audit trail
```

Everything below drives that pipeline through its real code path. Nothing is
mocked, and no step requires editing the database by hand.

## Setup, once

```bash
cd backend
alembic upgrade head
python -m app.utils.seed            # roles + demo employees and analysts
uvicorn app.main:app --reload
```

Startup seeds the synthetic bank and the classified resource registry
(idempotently — a second boot skips both).

Then, **as a SECURITY_ANALYST**:

```bash
curl -X POST "localhost:8000/api/v1/admin/demo/history?days=30" \
     -H "Authorization: Bearer $ANALYST_TOKEN"
```

This writes ~30 days of ordinary working activity for every demo employee,
recomputes every baseline, and trains the Isolation Forest. It is the step
people skip, and skipping it is why a fresh install appears to detect nothing:
with no telemetry there is no baseline to deviate from and no model to train, so
only the absolute-threshold rules can fire.

It refuses to run twice unless you pass `force=true`.

## The demo employees

| Email | Role | Normal login | Home city | Typical day |
| --- | --- | --- | --- | --- |
| `meera.krishnan@sentinel.in` | TELLER | 09:30 | Vijayawada | 22 searches, 14 views |
| `arjun.nair@sentinel.in` | RELATIONSHIP_MANAGER | 09:00 | Vijayawada | 30 searches, 20 views |
| `sunita.rao@sentinel.in` | BRANCH_MANAGER | 08:45 | Hyderabad | 12 searches, 9 views |
| `farhan.ali@sentinel.in` | COMPLIANCE_OFFICER | 09:15 | Vijayawada | 6 searches, 6 documents |
| `deepak.menon@sentinel.in` | OPERATIONS_MANAGER | 09:45 | Visakhapatnam | 9 searches, 12 transactions |

Each has a distinct working pattern, which is the point: a bank-wide average
would make every one of them look anomalous. Baselines are learned per employee
from their own history.

Scenarios default to `arjun.nair@sentinel.in`; pass `?email=` to target another.

## The eight scenarios

```bash
curl -X POST "localhost:8000/api/v1/admin/demo/scenario/combined_insider" \
     -H "Authorization: Bearer $ANALYST_TOKEN"
```

| Name | What it does | Expected |
| --- | --- | --- |
| `normal` | An ordinary working day: login, six searches, logout | **No alert.** The most important result in the suite. |
| `after_hours` | Login at 02:20 and three sensitive accesses | RULE-007 (HIGH) |
| `new_device` | Login and browsing from `DEVICE-X9999` | RULE-003 (MEDIUM) |
| `unusual_location` | Access from a city never used before | RULE-001, RULE-010 |
| `mass_lookup` | Bulk enumeration of the customer book | RULE-004, RULE-005 |
| `sensitive_download` | Repeated HIGHLY_CONFIDENTIAL downloads | RULE-006, RULE-008 |
| `usb_transfer` | A sensitive file copied to `USB-DEMO-1024` | RULE-009 (CRITICAL) |
| `combined_insider` | Reconnaissance → enumeration → collection → exfiltration | **CRITICAL** |

### Reading the response

The shape below is the response contract. **The numbers in it are illustrative,
not captured output** — exact scores depend on the employee's learned baseline
and whether a model is trained. What the test suite pins is the *level* each
scenario reaches, not the exact figure.

```jsonc
{
  "scenario": "combined_insider",
  "employee": { "name": "Arjun Nair", "employeeCode": "EMP-00002" },

  "risk": {
    "score": 84.2,                  // illustrative
    "level": "CRITICAL",            // ← this is the assertion
    "ruleScore": 90.0,
    "mlScore": 61.4,
    "baselineScore": 72.0,
    "reasons": [
      "[RULE-009] Simulated transfer of customer_risk_report.pdf (1887436 bytes) …",
      "[RULE-008] 6 distinct sensitive resources accessed within 15 minutes …"
    ],
    "ruleHits": [ /* every rule that fired, with evidence */ ]
  },

  "progression": [
    { "step": "login",               "score": 12.0, "level": "LOW",      "rules": [] },
    { "step": "customer_lookup",     "score": 38.5, "level": "MODERATE", "rules": ["RULE-004"] },
    { "step": "sensitive_downloads", "score": 66.1, "level": "HIGH",     "rules": ["RULE-004","RULE-006","RULE-008"] },
    { "step": "usb_transfer",        "score": 84.2, "level": "CRITICAL", "rules": [ /* … */ "RULE-009","RULE-011"] }
  ],

  "alert": { "id": "…", "severity": "CRITICAL", "status": "OPEN" },
  "ml": { "score": 61.4, "available": true, "contributions": [ /* per-feature sigmas */ ] },
  "eventsConsidered": 38,
  "synthetic": true,
  "executedBy": { "name": "Security Analyst" }
}
```

**`progression` is the demonstration.** The score climbs
LOW → MODERATE → HIGH → CRITICAL across checkpoints, so the escalation is shown
rather than asserted. Each entry names the rules active at that step.

Scoring runs at a few checkpoints rather than on every event — scoring all 38
combined-scenario events individually would repeat the same 24-hour window
analysis 38 times for one answer.

### Why `usb_transfer` matters

It is the clearest single-signal case. RULE-009 contributes 38.0 with severity
CRITICAL, which alone sits below the 41.0 alert threshold. Two mechanisms make
it alert anyway:

1. Corroboration from the model and the baseline fills the headroom above the
   rule score.
2. The **severity floor** guarantees a CRITICAL rule scores at least 61.

Without the floor this scenario raised **no alert at all**: RULE-009's 38.0,
passed through the old renormalised blend, landed below the 41.0 threshold —
and worse, `sync_alert` derives alert severity from the composite *level*, so a
CRITICAL-severity detection would have produced a MEDIUM alert. A rule that
names an act as CRITICAL and then files it as a middle-severity non-event is
contradicting itself. The floor is the fix, and `tests/test_risk_engine.py` pins
it.

### Why `normal` matters more

A detection system that fires on ordinary work is worse than none, because
analysts learn to ignore it. `normal` is asserted in
`tests/test_detection_pipeline.py::test_normal_working_day_raises_no_alert`.

## Resetting between runs

Each scenario clears the employee's carried risk first (`reset=true`, the
default), so a result is attributable to that scenario. This matters because
scores decay over 24 hours: replaying a scenario against a previously-targeted
employee would otherwise inherit the earlier score and demonstrate nothing.

The reset **appends** a zero-score row and an audit note. It does not delete the
scores, alerts or events that came before — the history stays intact and
visible, which is what makes the trail worth having.

Pass `?reset=false` to see the score compound across scenarios instead.

## Running the whole story

```bash
API=localhost:8000/api/v1
AUTH="Authorization: Bearer $ANALYST_TOKEN"

for s in normal after_hours new_device unusual_location \
         mass_lookup sensitive_download usb_transfer combined_insider; do
  curl -s -X POST "$API/admin/demo/scenario/$s" -H "$AUTH" \
    | jq -r '"\(.scenario): \(.risk.score) \(.risk.level)  [\(.progression | map(.level) | join(" → "))]"'
done
```

```
normal:             LOW        [LOW → LOW]
after_hours:        ELEVATED   [LOW → ELEVATED]
new_device:         MODERATE   [LOW → MODERATE]
unusual_location:   ELEVATED   [LOW → ELEVATED]
mass_lookup:        HIGH       [LOW → MODERATE → HIGH]
sensitive_download: HIGH       [LOW → MODERATE → HIGH]
usb_transfer:       HIGH       [LOW → HIGH]
combined_insider:   CRITICAL   [LOW → MODERATE → HIGH → CRITICAL]
```

**These levels are the expected outcome, not captured output.** They follow from
the rules each scenario fires and the severity floor — `usb_transfer` reaches
HIGH because RULE-009 is CRITICAL, and `combined_insider` reaches CRITICAL
because several CRITICAL rules fire together — but the suite has not yet been
executed against them, so treat this table as the specification the tests should
confirm rather than a log. Exact scores depend on the employee's learned
baseline and whether a model is trained.

## The analyst's side

```
GET  /api/v1/admin/dashboard                    cards and charts
GET  /api/v1/admin/alerts?sort=risk             the queue, worst first
GET  /api/v1/admin/alerts/{id}                  full case file (audits VIEW_ALERT)
GET  /api/v1/admin/employees                    roster ranked by risk
GET  /api/v1/admin/employees/{id}               one employee, all history
GET  /api/v1/admin/threats                      the chronological timeline
GET  /api/v1/admin/audit-logs                   the append-only trail
POST /api/v1/admin/alerts/{id}/investigate      OPEN → INVESTIGATING
POST /api/v1/admin/alerts/{id}/notes            {"note": "…"}
POST /api/v1/admin/alerts/{id}/resolve          {"resolutionReason": "…", "outcome": "RESOLVED"}
```

The employee detail view is where the promise of the project is kept: profile,
current risk, risk history graph, login history, location history, device
history, customer access, sensitive-resource access, downloads, USB events,
alerts, and the full activity timeline — for one person, in one place.

## Demonstrating the audit trail

```bash
# 1. Run a scenario
curl -s -X POST "$API/admin/demo/scenario/combined_insider" -H "$AUTH" | jq .alert.id

# 2. Investigate it
curl -s -X POST "$API/admin/alerts/$ALERT_ID/investigate" -H "$AUTH"

# 3. Add a finding
curl -s -X POST "$API/admin/alerts/$ALERT_ID/notes" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"note":"Confirmed with the branch manager: no scheduled off-hours access."}'

# 4. Resolve it
curl -s -X POST "$API/admin/alerts/$ALERT_ID/resolve" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"resolutionReason":"Employee confirmed working late on a sanctioned audit.","outcome":"RESOLVED"}'

# 5. Read the trail — every step above is there, and cannot be edited or deleted
curl -s "$API/admin/audit-logs" -H "$AUTH" | jq '.items[] | {action, description}'
```

Resolution requires a reason. An unexplained closure is not a record an
investigator can defend six months later, so the field is mandatory rather than
encouraged.

## What the demo cannot show

Stated so the boundary is clear:

- **No real endpoint surveillance.** USB events are rows written by
  `POST /api/v1/simulation/usb/*`. Nothing enumerates hardware.
- **No precise location.** Events carry a city and country name. There are no
  coordinates, no GPS, no IP geolocation lookup. RULE-010 compares *city change
  within an interval* rather than computing real distance, and marks its
  evidence `"approximate": true`.
- **No rate limiting.** Spec §24 is not implemented; see `docs/security.md`.
- **The security-console UI is partially wired.** The employee portal and login
  are live against the API. The six original console views still render from
  `src/data/mock.ts`; the endpoints above are what they will call.
