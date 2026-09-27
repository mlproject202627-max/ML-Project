# Detection & ML

This document covers the two detection halves — the deterministic rules and the
Isolation Forest — and the risk engine that combines them. The arrangement
matters more than either part.

## The governing principle

> *"Do not blindly trust ML predictions."* — spec §12

A model fitted on unlabelled data can tell you that someone's behaviour is
statistically unusual. It cannot tell you they are stealing, because it has
never seen a theft. The design follows from that:

- Rules are the **base** score and the **explanation**.
- ML is **corroboration** that can only add, never subtract, never override.
- Statistics alone can never exceed the ELEVATED band (41–60). Unusual is not
  the same as malicious, and the engine is built so that it cannot pretend
  otherwise.
- An untrained model contributes nothing rather than contributing zero.

## Part 1 — Rule engine (`ml/rule_engine.py`)

Eleven rules over a trailing 24-hour window of one employee's telemetry. Each
hit carries a rule id, a severity, a risk contribution, a one-line explanation,
and the ids of the events that fired it.

| Rule | Name | Severity | Risk | Fires when |
| --- | --- | --- | --- | --- |
| RULE-001 | Unusual location | HIGH | 14.0 | Access from a city/country absent from the employee's baseline |
| RULE-002 | Unusual login time | MEDIUM | 10.0 | Login ≥ 2.5σ from the usual login hour |
| RULE-003 | New device | MEDIUM | 12.0 | Activity from an unseen device fingerprint |
| RULE-004 | Excessive customer searches | HIGH | 16.0 | Searches ≥ max(40, 3× baseline daily rate) |
| RULE-005 | Mass record access | HIGH | 24.0 | Distinct customers ≥ max(20, 3× baseline), capped at 75% of the book |
| RULE-006 | Sensitive document download | HIGH / CRITICAL | 26.0 | ≥5 sensitive downloads, or any single RESTRICTED one |
| RULE-007 | After-hours sensitive access | HIGH | 22.0 | Sensitive access outside the employee's working window |
| RULE-008 | Rapid sensitive resource access | CRITICAL | 28.0 | ≥5 distinct sensitive resources within 15 minutes |
| RULE-009 | Sensitive file transfer to removable media | CRITICAL | 38.0 | A sensitive file copied to a USB device |
| RULE-010 | Impossible-travel style anomaly | CRITICAL | 30.0 | Different cities within 120 minutes |
| RULE-011 | Multiple simultaneous anomalies | CRITICAL | 15.0 | ≥3 distinct rules fired in the same window |

Four decisions worth explaining, because each fixes a failure mode that is easy
to ship without noticing.

**Thresholds are baseline-relative.** An employee who normally searches 60
customers a day is not suspicious at 60. RULE-004 and RULE-005 compare against
`EmployeeBaseline` and fall back to absolute floors only for cold-start
accounts.

**RULE-005 is capped at 75% of the customer book.** Without the cap, a heavy
user of a 48-customer book needs to touch 66 distinct records to trip a
threshold of 20×3 — more than exist. The rule becomes permanently unreachable
for *exactly the employees best placed to abuse it*, which is the worst possible
failure direction. `POPULATION_CEILING` keeps the threshold inside the
population it measures, and the explanation says when the cap applied.

**Thresholds are shared with the demo generator.** `search_burst_threshold()` and
`mass_access_threshold()` are exported so `seed_scenarios.py` sizes its
synthetic bursts from the same number the rule tests against. A hard-coded count
in the generator would silently stop tripping the rule the moment a threshold
was tuned.

**RULE-010 is deliberately style-over-substance.** The system stores approximate
cities, not coordinates — spec §7 forbids invasive location tracking. So this
compares *city change within a short interval* rather than computing geodesic
distance, and marks its evidence `"approximate": True`. It flags a pattern for a
human to read; it does not claim to prove anything.

**A rule that raises is logged, not swallowed.** `evaluate_context` catches per
rule and calls `logger.exception`. Silently skipping a broken rule would leave a
hole in detection that nothing surfaces. See spec rule 14.

RULE-011 is evaluated after the other ten because it reads their output — the
only ordering dependency in the engine. It counts *distinct* rules, so repeating
one behaviour cannot trip it.

## Part 2 — Feature engineering (`ml/features.py`)

15 features per (employee, 24h window), and the same vector feeds both the model
and (indirectly) the rules' reasoning:

| Feature | Meaning |
| --- | --- |
| `login_hour` | Hour of first login |
| `location_change` | Access from a location outside the baseline |
| `country_change` | Access from an outside country |
| `new_device` | Activity from an unseen device |
| `failed_login_count` | Failed authentications |
| `records_accessed` | Total records touched |
| `sensitive_records_accessed` | Records at CONFIDENTIAL or above |
| `downloads` | Document downloads |
| `download_volume` | Megabytes downloaded |
| `usb_events` | Removable-media events |
| `after_hours` | Events outside working hours |
| `session_duration` | Minutes |
| `unique_customers` | Distinct customers touched |
| `unique_resources` | Distinct resources touched |
| `department_access_count` | Distinct departments accessed |

The last one is the quiet workhorse: an employee reaching across departments
they have no business in is a stronger signal than raw volume, and it is what
"typical department/resource access" in spec §8 is for.

## Part 3 — Isolation Forest (`ml/anomaly.py`)

`IsolationForest(n_estimators=200, contamination="auto", random_state=42)` —
`random_state` fixed so a demonstration produces the same scores twice.

### Calibrating the score

Isolation Forest's `decision_function` has no absolute meaning: its scale
depends on `n_estimators` and `contamination`, so "−0.14" tells you nothing
about how bad a day was. So the raw margin is converted to a robust z-score
against the *training population's own* median and MAD, then squashed through a
logistic:

```
z      = (raw_margin − training_median) / (1.4826 × training_MAD)
score  = 100 / (1 + e^(−z))
```

Which gives a score with a stable meaning regardless of hyperparameters:

| Score | Reading |
| --- | --- |
| 50 | Exactly typical — the median training day |
| ~73 | 1σ out |
| ~88 | 2σ out |
| ~95 | 3σ out |
| →100 | Far outside the training population |

Calibration constants are measured at training time and persisted with the
model, so a loaded artefact scores identically to the one that produced it.

### Training

`build_training_matrix` produces one row per (employee, *day*) from stored
telemetry. Two choices:

- **Per-employee history, not a bank-wide average.** A teller's normal Tuesday
  and a compliance officer's normal Tuesday are different days. Training on the
  pooled population would make each of them look anomalous.
- **Days with fewer than three events are skipped.** A two-event day carries no
  behavioural shape; including it would teach the model that quiet days are
  outliers — which is precisely the wrong lesson.

`MIN_TRAINING_ROWS = 50`. Below that the model declines to make claims and
reports `available=False` rather than guessing on an unrepresentative sample.

### Explainability

`explain()` reports the features furthest from the training distribution in
robust sigmas:

> *Documents downloaded: 14 (typical: 3.1) — 4.1σ above*
> *Distinct customers touched: 47 (typical: 8.4) — 3.8σ above*

This is a claim the model can actually support — it is a statement about the
training data, which is what the model was fitted on. SHAP values over a forest
fitted on *unlabelled* data would not be more truthful, only more elaborate:
SHAP explains a model's output, and here the model's output is "this looks
unusual", not "this person is malicious". The admin-facing explanation comes
from the rules, which name behaviour rather than deviation.

## Part 4 — The risk engine (`app/services/risk.py`)

### The formula

```
risk = rule_score + (100 − rule_score) × corroboration × 0.50
```

where

```
corroboration = (0.30 × ml_score + 0.20 × baseline_score) / (0.30 + 0.20)
                … over whichever components are available
```

and then

```
risk = max(risk, severity_floor(hits))
```

### Why not a weighted average

The obvious formulation — `0.5×rules + 0.3×ml + 0.2×baseline` — has a quiet
failure mode. When a component is missing, the remaining weights renormalise and
**the achievable maximum falls**. With no ML model trained, which is every fresh
install until someone runs the training command, the cap is:

```
0.5 × 100 / 0.7 = 71.4   →  HIGH
```

So the CRITICAL band (81–100) was unreachable by construction. The
specification's combined insider-threat scenario could not have reached its
expected severity *no matter what the employee did*. That is the kind of bug
that survives review, because every individual number looks reasonable.

Formulating the rule score as the **base** and the other signals as headroom
above it fixes this: corroboration only ever adds, so an absent signal lowers
nothing.

### The severity floor

A rule's severity is a claim about the behaviour it names, and the composite
must not contradict it. Without a floor, RULE-009 — a RESTRICTED file copied to
removable media, severity CRITICAL — contributed 38.0, and the old blend placed
it in the high twenties to mid thirties: **below the 41.0 alert threshold either
way.** It raised no alert at all.

There was a second, quieter half to this bug. `sync_alert` derives the alert's
severity from the composite *level*, not from the rule — so a CRITICAL-severity
detection would have produced a MEDIUM alert even had it crossed the threshold.
A rule that names an act as CRITICAL and then files it as a middle-severity
non-event is contradicting itself twice.

| Severity | Floor | Rationale |
| --- | --- | --- |
| CRITICAL | 61 (HIGH) | A CRITICAL finding is CRITICAL however quiet the statistics around it |
| HIGH | 41 (ELEVATED) | The alert threshold — a HIGH rule must reach the queue |
| MEDIUM / LOW | 0 | No floor |

The floor reads the *set* of distinct rules, never the count, so repeating one
behaviour still cannot inflate the score. Guarantee 1 survives.

### The four guarantees

The engine is built to hold these. Each is covered by a test in
`tests/test_risk_engine.py`.

1. **Repeated identical events cannot inflate risk indefinitely.** Time-decay
   (`DECAY_HALF_LIFE_HOURS = 24`) and the set-based floor together mean doing
   the same thing forty times scores the same as doing it once.
2. **The ML model is never trusted on its own.** With `rule_score = 0`, the
   maximum achievable is ELEVATED. Statistics cannot raise an alert by
   themselves.
3. **Missing signals do not dilute the score.** No model, no baseline, neither —
   the rule score stands undiluted.
4. **Severity is not negotiable.** The floor above.

### ML discounting when the rules have nothing to say

`score_ml` applies a halving discount (`ML_DISCOUNT = 0.5`) when the **rule
score** is below `ML_TRUST_FLOOR = 20.0` — that is, when the observable
behaviour is unremarkable and the model's opinion is the only thing left
arguing for an incident.

This is the mechanism behind guarantee 2, and it is worth being precise about
the direction: the discount keys off *rule* evidence, not off the model's own
confidence. A model is not penalised for being unsure — it is discounted for
being uncorroborated. An outlier the rules cannot explain is a prompt to look,
not a verdict.

Combine that with the `SECONDARY_SHARE = 0.50` cap on how much corroboration can
ever contribute, and statistics alone cannot exceed the ELEVATED band.

## Part 5 — The pipeline

```
Activity recorded
   │
   ├─▶ collect_window()          24h of this employee's events
   │
   ├─▶ extract_features()        15-dim vector
   │
   ├─▶ rule_engine.evaluate()    11 rules → RuleHit[]
   │        └─ score_rules()     → 0–100
   │
   ├─▶ anomaly.detect()          Isolation Forest → 0–100 (or available=False)
   │
   ├─▶ baseline deviation        robust z against the employee's own means
   │
   ├─▶ risk.combine()            base + corroboration
   │   risk.severity_floor()     floor by most severe rule
   │   risk.build_reasons()      top N human-readable reasons
   │
   ├─▶ RiskScore row             append-only, with component subtotals
   │
   └─▶ sync_alert()              ≥41 → refresh or create the employee's alert
```

Every step is inspectable in the API response: `rule_score`, `ml_score` and
`baseline_score` are stored separately on the `risk_scores` row, so the console
can show *"rules 45 · ML 22 · baseline 14"* rather than one opaque number.

## Legacy components

`ml/rules.py` (8 rules), `ml/risk_engine.py` and `ml/inference.py` are the
original detection attempt, predating the detection foundation. They remain
reachable through `POST /api/v1/ml/predict` and are still used by the agent
ingestion path.

They are **not** what scores risk, and nothing they produce raises an alert.
`/api/v1/ml/status` reports `ml.anomaly`, not the `ml.inference` stub — an
earlier version reported the stub, which told an operator about a model
(`sentinel-ueba-v1`) that plays no part in any detection.

## Running it

```bash
# Train from whatever telemetry exists (needs ≥50 employee-days)
curl -X POST "localhost:8000/api/v1/admin/demo/history?days=30" \
     -H "Authorization: Bearer $ANALYST_TOKEN"

# Inspect
curl localhost:8000/api/v1/ml/status -H "Authorization: Bearer $ANALYST_TOKEN"
curl localhost:8000/api/v1/ready
```

The artefact lands at `backend/models/isolation_forest.joblib` (override with
`MODEL_PATH`) with a `.json` sidecar recording feature names, training rows and
timestamp, so provenance is inspectable without unpickling. Both are gitignored
— a model is a build product, not source.
