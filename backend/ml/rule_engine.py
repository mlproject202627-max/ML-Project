"""Rule-based threat engine (spec §9).

Eleven deterministic rules run over a trailing window of one employee's
telemetry. Rules are the *explainable* half of detection: every hit carries a
rule id, the event that fired it, a severity, a risk contribution and a
sentence an administrator can read without knowing anything about ML.

Design notes:

- **Window, not event.** Several rules are aggregate by nature ("excessive
  searches", "mass record access"). Running over a window keeps one code path.
- **Baseline-relative where possible.** An employee who normally searches 60
  customers a day is not suspicious at 60. Thresholds lean on
  `EmployeeBaseline` when one exists and fall back to absolute defaults for
  cold-start accounts.
- **Explanations name numbers.** "42 customer records in 30 minutes (typical
  for this employee: 6)" is actionable. "Anomalous activity detected" is not.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.resource import is_sensitive, classification_rank

logger = logging.getLogger("sentinel.ml.rules")

# ---------------------------------------------------------------------------
# Thresholds — module constants so tests and docs can cite them directly.
# ---------------------------------------------------------------------------

DEFAULT_WINDOW_HOURS = 24

#: RULE-004 / RULE-005 — absolute floors when no baseline exists.
SEARCH_BURST_THRESHOLD = 40          # customer searches inside the window
MASS_ACCESS_THRESHOLD = 20           # distinct customers viewed inside the window
#: Multiplier applied to the employee's own baseline when one exists.
BASELINE_MULTIPLIER = 3.0

#: RULE-005 — how much of the customer book counts as "the whole thing". The
#: baseline-relative threshold is capped at this fraction so it stays reachable.
POPULATION_CEILING = 0.75

#: RULE-006 — downloads of CONFIDENTIAL-or-above that trip the rule.
SENSITIVE_DOWNLOAD_THRESHOLD = 5

#: RULE-008 — distinct sensitive resources inside RAPID_WINDOW_MINUTES.
RAPID_SWEEP_RESOURCES = 5
RAPID_WINDOW_MINUTES = 15

#: RULE-002 — how many standard deviations off the usual login hour.
LOGIN_HOUR_Z_THRESHOLD = 2.5

#: RULE-010 — different city within this many minutes is "impossible travel".
IMPOSSIBLE_TRAVEL_MINUTES = 120

#: RULE-011 — distinct rules that must fire before the composite escalates.
COMPOSITE_RULE_THRESHOLD = 3


@dataclass
class RuleHit:
    """One rule firing, with everything the admin portal needs to explain it."""

    rule_id: str
    name: str
    severity: str            # LOW | MEDIUM | HIGH | CRITICAL
    risk: float              # contribution on the 0–100 risk scale
    explanation: str
    evidence: dict = field(default_factory=dict)
    event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ruleId": self.rule_id,
            "name": self.name,
            "severity": self.severity,
            "risk": self.risk,
            "explanation": self.explanation,
            "evidence": self.evidence,
            "eventIds": self.event_ids,
        }


@dataclass
class RuleContext:
    """Everything the rules read, assembled once per evaluation."""

    employee_id: str
    events: Sequence[Activity]
    baseline: Optional[object] = None
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    now: Optional[datetime] = None
    #: How many distinct customer records exist. RULE-005 is bounded by this:
    #: a threshold above the population size can never be reached by anyone.
    customer_population: Optional[int] = None

    def of_type(self, *types: str) -> list[Activity]:
        wanted = set(types)
        return [e for e in self.events if e.event_type in wanted]

    def sensitive(self) -> list[Activity]:
        return [e for e in self.events if is_sensitive(e.sensitivity or "INTERNAL")]

    def in_last_minutes(self, minutes: int) -> list[Activity]:
        cutoff = (self.now or datetime.now(timezone.utc)) - timedelta(minutes=minutes)
        return [e for e in self.events if _aware(e.timestamp) >= cutoff]

    def _baseline_mean(self, attr: str, fallback: float) -> float:
        if self.baseline is None:
            return fallback
        value = getattr(self.baseline, attr, None)
        return fallback if value in (None, 0) else float(value)


def _aware(dt: Optional[datetime]) -> datetime:
    """SQLite hands back naive datetimes; compare in one frame."""
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _event_id(event: Activity) -> str:
    return str(event.id)


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def rule_001_unusual_location(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 1 — access from a city/country this employee has never used."""
    baseline = ctx.baseline
    if baseline is None:
        return None

    seen: dict[str, Activity] = {}
    for event in ctx.events:
        city = (event.city or "").strip()
        if not city or city in seen:
            continue
        if not baseline.is_known_location(city, event.country):
            seen[city] = event

    if not seen:
        return None

    cities = ", ".join(sorted(seen))
    sample = next(iter(seen.values()))
    return RuleHit(
        rule_id="RULE-001",
        name="Unusual location",
        severity="HIGH",
        risk=14.0,
        explanation=(
            f"Access from {cities}, which is outside this employee's usual "
            f"locations. First seen {_fmt(sample.timestamp)} from IP "
            f"{sample.source_ip or 'unknown'}."
        ),
        evidence={"cities": sorted(seen), "knownLocations": list((baseline.normal_locations or {}).keys())},
        event_ids=[_event_id(e) for e in seen.values()],
    )


def rule_002_unusual_login_time(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 2 — logging in far outside the employee's normal hour envelope."""
    logins = ctx.of_type("LOGIN_SUCCESS")
    if not logins:
        return None

    baseline = ctx.baseline
    if baseline is None:
        # Cold start: fall back to a plain working-hours test.
        odd = [e for e in logins if not (6.0 <= _aware(e.timestamp).hour + _aware(e.timestamp).minute / 60.0 <= 22.0)]
        if not odd:
            return None
        sample = odd[0]
        return RuleHit(
            rule_id="RULE-002",
            name="Unusual login time",
            severity="MEDIUM",
            risk=10.0,
            explanation=(
                f"Login at {_fmt(sample.timestamp)} is outside normal working "
                f"hours. This employee has no established baseline yet, so the "
                f"rule used a 06:00–22:00 default."
            ),
            evidence={"loginHour": _aware(sample.timestamp).hour, "baselineKnown": False},
            event_ids=[_event_id(sample)],
        )

    outliers = []
    for event in logins:
        ts = _aware(event.timestamp)
        hour = ts.hour + ts.minute / 60.0
        if abs(baseline.login_hour_zscore(hour)) >= LOGIN_HOUR_Z_THRESHOLD:
            outliers.append(event)

    if not outliers:
        return None

    sample = outliers[0]
    ts = _aware(sample.timestamp)
    hour = ts.hour + ts.minute / 60.0
    z = baseline.login_hour_zscore(hour)
    return RuleHit(
        rule_id="RULE-002",
        name="Unusual login time",
        severity="MEDIUM",
        risk=10.0,
        explanation=(
            f"Login at {ts.strftime('%H:%M')} is {abs(z):.1f} standard "
            f"deviations from this employee's normal login hour of "
            f"{baseline.avg_login_hour:.1f}:00."
        ),
        evidence={"loginHour": round(hour, 2), "baselineHour": baseline.avg_login_hour, "zScore": round(z, 2)},
        event_ids=[_event_id(e) for e in outliers],
    )


def rule_003_new_device(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 3 — activity from a device fingerprint not seen before."""
    flagged = [e for e in ctx.events if (e.extra_metadata or {}).get("new_device") or e.event_type == "NEW_DEVICE_DETECTED"]
    if not flagged:
        return None

    labels = sorted({(e.device or "unknown device") for e in flagged})
    sample = flagged[0]
    meta = sample.extra_metadata or {}
    return RuleHit(
        rule_id="RULE-003",
        name="New device",
        severity="MEDIUM",
        risk=12.0,
        explanation=(
            f"Activity from unrecognised device {', '.join(labels)}"
            + (f" ({meta.get('browser')})" if meta.get("browser") else "")
            + f". First seen {_fmt(sample.timestamp)}."
        ),
        evidence={"devices": labels, "firstSeen": _iso(sample.timestamp)},
        event_ids=[_event_id(e) for e in flagged],
    )


def rule_004_excessive_customer_searches(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 4 — search volume far above this employee's normal rate."""
    searches = ctx.of_type("CUSTOMER_SEARCH")
    if not searches:
        return None

    typical = ctx._baseline_mean("avg_customer_searches", 0.0)
    threshold = search_burst_threshold(ctx.baseline)

    if len(searches) < threshold:
        return None

    hours = max(1.0, (ctx.window_end - ctx.window_start).total_seconds() / 3600.0) if ctx.window_start and ctx.window_end else 24.0
    return RuleHit(
        rule_id="RULE-004",
        name="Excessive customer searches",
        severity="HIGH",
        risk=16.0,
        explanation=(
            f"{len(searches)} customer searches in {hours:.0f} hours, against a "
            f"threshold of {threshold:.0f}"
            + (f" (this employee normally averages {typical:.1f} per day)." if typical else ".")
        ),
        evidence={"searchCount": len(searches), "threshold": round(threshold, 1), "baselineDaily": typical},
        event_ids=[_event_id(e) for e in searches],
    )


def _baseline_value(baseline, attr: str) -> float:
    """A baseline mean, or 0.0 when there is no baseline or no observation yet."""
    value = getattr(baseline, attr, None) if baseline is not None else None
    return 0.0 if value in (None, 0) else float(value)


def search_burst_threshold(baseline) -> float:
    """Customer searches within the window required by RULE-004.

    Exposed so the demo scenario generator sizes its synthetic burst from the
    same number the rule tests against, rather than a hard-coded count that
    would silently stop tripping the rule when a threshold is tuned.
    """
    typical = _baseline_value(baseline, "avg_customer_searches")
    return max(SEARCH_BURST_THRESHOLD, typical * BASELINE_MULTIPLIER) if typical else float(SEARCH_BURST_THRESHOLD)


def mass_access_threshold(baseline, population: Optional[int]) -> tuple[float, bool]:
    """Distinct customers required by RULE-005, and whether it had to be capped.

    The cap keeps the threshold inside the population it measures: a heavy user
    of a 48-customer book would otherwise need to touch 66 distinct records to
    trip the rule — more than exist — leaving it permanently unreachable for
    exactly the employees best placed to abuse it.
    """
    typical = _baseline_value(baseline, "avg_unique_customers")
    threshold = max(MASS_ACCESS_THRESHOLD, typical * BASELINE_MULTIPLIER) if typical else float(MASS_ACCESS_THRESHOLD)
    if population and threshold > population * POPULATION_CEILING:
        return max(float(MASS_ACCESS_THRESHOLD), population * POPULATION_CEILING), True
    return float(threshold), False


def rule_005_mass_record_access(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 5 — touching an unusually wide set of distinct customer records."""
    views = ctx.of_type("CUSTOMER_VIEW", "ACCOUNT_VIEW", "TRANSACTION_VIEW")
    if not views:
        return None

    customers = {str(e.customer_id) for e in views if e.customer_id}
    typical = _baseline_value(ctx.baseline, "avg_unique_customers")
    threshold, capped = mass_access_threshold(ctx.baseline, ctx.customer_population)

    if len(customers) < threshold:
        return None

    return RuleHit(
        rule_id="RULE-005",
        name="Mass record access",
        severity="HIGH",
        risk=24.0,
        explanation=(
            f"{len(customers)} distinct customer records accessed in the "
            f"monitoring window, against a threshold of {threshold:.0f}"
            + (f" (this employee normally touches {typical:.1f})." if typical else ".")
            + (f" Threshold is capped at {POPULATION_CEILING:.0%} of the "
               f"{ctx.customer_population}-record customer book." if capped else "")
        ),
        evidence={
            "uniqueCustomers": len(customers),
            "threshold": round(threshold, 1),
            "baselineDaily": typical,
            "population": ctx.customer_population,
            "thresholdCapped": capped,
        },
        event_ids=[_event_id(e) for e in views],
    )


def rule_006_sensitive_document_download(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 6 — downloading confidential-or-above documents."""
    downloads = [
        e for e in ctx.of_type("DOCUMENT_DOWNLOAD", "SENSITIVE_DATA_ACCESS")
        if is_sensitive(e.sensitivity or "INTERNAL")
    ]
    if not downloads:
        return None

    highest = max((classification_rank(e.sensitivity or "INTERNAL") for e in downloads), default=0)
    # A single RESTRICTED download is enough; lower tiers need volume.
    if highest < classification_rank("HIGHLY_CONFIDENTIAL") and len(downloads) < SENSITIVE_DOWNLOAD_THRESHOLD:
        return None

    names = sorted({e.resource for e in downloads if e.resource})
    return RuleHit(
        rule_id="RULE-006",
        name="Sensitive document download",
        severity="HIGH" if highest < classification_rank("RESTRICTED") else "CRITICAL",
        risk=26.0,
        explanation=(
            f"{len(downloads)} download(s) of sensitive material, up to "
            f"{_rank_name(highest)} classification"
            + (f": {', '.join(names[:3])}" if names else "")
            + "."
        ),
        evidence={"downloads": len(downloads), "highestClassification": _rank_name(highest), "resources": names},
        event_ids=[_event_id(e) for e in downloads],
    )


def rule_007_after_hours_sensitive_access(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 7 — sensitive access outside the employee's working hours."""
    flagged = [
        e for e in ctx.events
        if (e.extra_metadata or {}).get("after_hours_sensitive")
        or (e.event_type == "AFTER_HOURS_ACCESS" and is_sensitive(e.sensitivity or "INTERNAL"))
    ]
    if not flagged:
        return None

    sample = flagged[0]
    ts = _aware(sample.timestamp)
    return RuleHit(
        rule_id="RULE-007",
        name="After-hours sensitive access",
        severity="HIGH",
        risk=22.0,
        explanation=(
            f"{len(flagged)} sensitive access(es) outside working hours, "
            f"starting {ts.strftime('%Y-%m-%d %H:%M')}"
            + (f" — {sample.resource}" if sample.resource else "")
            + f". Recorded sensitivity: {sample.sensitivity}."
        ),
        evidence={"count": len(flagged), "firstAt": _iso(sample.timestamp), "sensitivity": sample.sensitivity},
        event_ids=[_event_id(e) for e in flagged],
    )


def rule_008_rapid_sensitive_sweep(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 8 — many distinct sensitive resources touched in minutes."""
    recent = ctx.in_last_minutes(RAPID_WINDOW_MINUTES)
    sensitive_recent = [e for e in recent if is_sensitive(e.sensitivity or "INTERNAL")]

    # Distinct *targets*, not events. Key on the stable human label when the
    # events carry one; `resource_id` differs per event for ad-hoc targets
    # (each access mints a fresh row), so it would count re-reads of the same
    # document as distinct resources.
    keys = {(e.resource or (str(e.resource_id) if e.resource_id else None)) for e in sensitive_recent}
    keys.discard(None)
    if len(keys) < RAPID_SWEEP_RESOURCES:
        return None

    return RuleHit(
        rule_id="RULE-008",
        name="Rapid sensitive resource access",
        severity="CRITICAL",
        risk=28.0,
        explanation=(
            f"{len(keys)} distinct sensitive resources accessed within "
            f"{RAPID_WINDOW_MINUTES} minutes — a rate consistent with bulk "
            f"collection rather than normal casework."
        ),
        evidence={"distinctResources": len(keys), "windowMinutes": RAPID_WINDOW_MINUTES},
        event_ids=[_event_id(e) for e in sensitive_recent],
    )


def rule_009_usb_sensitive_transfer(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 9 — simulated copy of sensitive material to removable media."""
    transfers = [
        e for e in ctx.events
        if e.event_type in ("SENSITIVE_FILE_TRANSFER", "FILE_TRANSFER_SIMULATED")
        and (e.event_type == "SENSITIVE_FILE_TRANSFER" or is_sensitive(e.sensitivity or "INTERNAL"))
    ]
    if not transfers:
        return None

    sample = transfers[0]
    meta = sample.extra_metadata or {}
    size = meta.get("fileSize") or meta.get("file_size")
    return RuleHit(
        rule_id="RULE-009",
        name="Sensitive file transfer to removable media",
        severity="CRITICAL",
        risk=38.0,
        explanation=(
            f"Simulated transfer of {sample.resource or 'a sensitive file'}"
            + (f" ({size} bytes)" if size else "")
            + f" to removable device {sample.device or 'unknown'}"
            + f" at {_fmt(sample.timestamp)}."
            + (f" Classification: {sample.sensitivity}." if sample.sensitivity else "")
        ),
        evidence={
            "device": sample.device,
            "resource": sample.resource,
            "classification": sample.sensitivity,
            "fileSize": size,
        },
        event_ids=[_event_id(e) for e in transfers],
    )


def rule_010_impossible_travel(ctx: RuleContext) -> Optional[RuleHit]:
    """RULE 10 — two locations too far apart in too short a time.

    Deliberately style-over-substance: the demo stores approximate cities, not
    coordinates, so this compares *city change* within a short interval rather
    than computing real geodesic distance. It flags the pattern; the admin
    reads the two events and decides.
    """
    logins = sorted(
        [e for e in ctx.of_type("LOGIN_SUCCESS", "LOGIN_FAILURE") if e.city],
        key=lambda e: _aware(e.timestamp),
    )
    for previous, current in zip(logins, logins[1:]):
        if (previous.city or "").lower() == (current.city or "").lower():
            continue
        gap = (_aware(current.timestamp) - _aware(previous.timestamp)).total_seconds() / 60.0
        if 0 <= gap <= IMPOSSIBLE_TRAVEL_MINUTES:
            return RuleHit(
                rule_id="RULE-010",
                name="Impossible-travel style anomaly",
                severity="CRITICAL",
                risk=30.0,
                explanation=(
                    f"Authentication from {previous.city} at "
                    f"{_fmt(previous.timestamp)} followed by {current.city} at "
                    f"{_fmt(current.timestamp)} — {gap:.0f} minutes apart. "
                    f"Physically implausible for the same person."
                ),
                evidence={
                    "from": previous.city, "to": current.city,
                    "minutesApart": round(gap, 1),
                    "approximate": True,
                },
                event_ids=[_event_id(previous), _event_id(current)],
            )
    return None


def rule_011_multiple_simultaneous_anomalies(ctx: RuleContext, prior_hits: Sequence[RuleHit]) -> Optional[RuleHit]:
    """RULE 11 — several independent rules firing together.

    One weak signal is noise. Four weak signals in the same window is the
    shape of an actual insider incident, so this rule escalates the composite.
    """
    distinct = {hit.rule_id for hit in prior_hits}
    if len(distinct) < COMPOSITE_RULE_THRESHOLD:
        return None

    names = [hit.name for hit in prior_hits if hit.rule_id != "RULE-011"]
    event_ids: list[str] = []
    for hit in prior_hits:
        event_ids.extend(hit.event_ids)
    return RuleHit(
        rule_id="RULE-011",
        name="Multiple simultaneous anomalies",
        severity="CRITICAL",
        risk=15.0,
        explanation=(
            f"{len(distinct)} independent detection rules fired in the same "
            f"window: {', '.join(names)}. Correlated signals of this kind "
            f"indicate coordinated behaviour rather than an isolated mistake."
        ),
        evidence={"rulesFired": sorted(distinct), "count": len(distinct)},
        event_ids=event_ids,
    )


#: Evaluation order matters only for RULE-011, which reads the others' output.
RULES = (
    rule_001_unusual_location,
    rule_002_unusual_login_time,
    rule_003_new_device,
    rule_004_excessive_customer_searches,
    rule_005_mass_record_access,
    rule_006_sensitive_document_download,
    rule_007_after_hours_sensitive_access,
    rule_008_rapid_sensitive_sweep,
    rule_009_usb_sensitive_transfer,
    rule_010_impossible_travel,
)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def collect_events(
    db: Session,
    *,
    employee_id,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    now: Optional[datetime] = None,
) -> list[Activity]:
    """Load one employee's telemetry for the trailing window."""
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(hours=window_hours)
    return (
        db.query(Activity)
        .filter(Activity.user_id == employee_id, Activity.timestamp >= start, Activity.timestamp <= now)
        .order_by(Activity.timestamp.asc())
        .all()
    )


def evaluate_context(ctx: RuleContext) -> list[RuleHit]:
    """Run all rules against a prepared context. Pure — no database access.

    A rule that raises is logged and skipped rather than taking the other ten
    down with it, but it is never skipped *quietly* — a rule that has stopped
    working is a hole in detection, and the log is the only place that shows.
    """
    hits: list[RuleHit] = []
    for rule in RULES:
        try:
            hit = rule(ctx)
        except Exception:
            logger.exception("Rule %s failed; it contributed nothing to this assessment.", rule.__name__)
            hit = None
        if hit is not None:
            hits.append(hit)

    composite = rule_011_multiple_simultaneous_anomalies(ctx, hits)
    if composite is not None:
        hits.append(composite)
    return hits


def customer_population(db: Session) -> Optional[int]:
    """Count distinct customer records, for the RULE-005 reachability cap."""
    from app.models.banking import Customer

    try:
        return db.query(Customer).count() or None
    except Exception:
        logger.warning("Could not count the customer population; RULE-005 cap disabled.")
        return None


def evaluate(
    db: Session,
    *,
    user,
    window_hours: int = DEFAULT_WINDOW_HOURS,
    now: Optional[datetime] = None,
    events: Optional[Iterable[Activity]] = None,
) -> list[RuleHit]:
    """Convenience wrapper: load the window, attach the baseline, run the rules."""
    now = now or datetime.now(timezone.utc)
    ctx = RuleContext(
        employee_id=str(user.id),
        events=list(events) if events is not None else collect_events(
            db, employee_id=user.id, window_hours=window_hours, now=now
        ),
        baseline=getattr(user, "baseline", None),
        window_start=now - timedelta(hours=window_hours),
        window_end=now,
        now=now,
        customer_population=customer_population(db),
    )
    return evaluate_context(ctx)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RANK_NAMES = {0: "PUBLIC", 1: "INTERNAL", 2: "CONFIDENTIAL", 3: "HIGHLY_CONFIDENTIAL", 4: "RESTRICTED"}


def _rank_name(rank: int) -> str:
    return _RANK_NAMES.get(rank, "INTERNAL")


def _fmt(dt: Optional[datetime]) -> str:
    return _aware(dt).strftime("%Y-%m-%d %H:%M")


def _iso(dt: Optional[datetime]) -> str:
    return _aware(dt).isoformat()
