"""Centralised risk engine (spec §11, §12).

Turns three independent signals into one 0–100 score, one risk level and a
list of reasons a human can read.

The rule score is the **base**; the ML anomaly score and the baseline deviation
are **corroboration** that fills the headroom above it:

    risk = rule_score + (100 - rule_score) × corroboration × SECONDARY_SHARE

Four properties this engine is built to guarantee:

1. **Repeated identical events cannot inflate risk indefinitely.** Rule hits
   are deduplicated by `rule_id` — the same rule firing forty times in a window
   contributes exactly as much as it firing once — and the composite is a
   `max()` against the decayed previous score rather than a sum.
2. **The ML model is never trusted on its own.** An anomaly score with no rule
   hits behind it is halved, and corroboration can only ever contribute
   `SECONDARY_SHARE` of the score, so statistics alone top out in the ELEVATED
   band: statistically unusual is not the same as malicious.
3. **Missing signals do not dilute the score.** Because corroboration only ever
   *adds*, an unavailable ML model lowers nothing. (An earlier formulation as a
   renormalised weighted average did dilute: it capped the achievable score at
   71/100 whenever no model was trained, which is every fresh install, leaving
   the CRITICAL band unreachable by construction.)
4. **Severity is not negotiable.** A rule that reports CRITICAL is making a
   claim about the behaviour it names, so the composite cannot land in a lower
   band than the most severe hit implies. Without this a single unambiguous
   finding — a RESTRICTED file copied to removable media — passed through the
   old blend below the alert threshold and raised no alert at all, contradicting
   the rule that detected it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.risk_score import RiskScore, level_for_score
from ml.rule_engine import RuleHit

logger = logging.getLogger("sentinel.risk")

#: Relative influence of the *corroborating* signals on each other. The rule
#: score is deliberately absent: it is not weighted, it is the base that
#: corroboration is added to (see `combine`).
SECONDARY_WEIGHTS = {
    "ml": 0.30,         # statistical outlier detection
    "baseline": 0.20,   # how far this window sits from the employee's own normal
}

#: Most a perfect corroborating signal can add on top of the rule score. This is
#: what keeps the statistical signals from ever carrying a score unaided: with
#: no rule hits the composite cannot exceed this share of 100.
SECONDARY_SHARE = 0.50

#: A rule's severity is a claim about the behaviour it names, so the composite
#: is floored at the bottom of the band that severity implies. A CRITICAL hit
#: guarantees at least HIGH; a HIGH hit guarantees at least ELEVATED, which is
#: where the alert queue starts. Corroboration still decides how much *worse*
#: than the floor the score gets.
SEVERITY_FLOOR = {"CRITICAL": 61.0, "HIGH": 41.0, "MEDIUM": 0.0, "LOW": 0.0}

#: Below this rule score, the ML contribution is discounted (see property 2).
ML_TRUST_FLOOR = 20.0
ML_DISCOUNT = 0.5

#: Risk halves after this many hours without new signals.
DECAY_HALF_LIFE_HOURS = 24.0

MAX_REASONS = 8


@dataclass
class RiskAssessment:
    """The engine's output, before it is persisted as a `RiskScore` row."""

    score: float
    level: str
    rule_score: float
    ml_score: float
    baseline_score: float
    previous_score: Optional[float]
    change: float
    reasons: list[str]
    rule_hits: list[RuleHit]

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "level": self.level,
            "ruleScore": round(self.rule_score, 2),
            "mlScore": round(self.ml_score, 2),
            "baselineScore": round(self.baseline_score, 2),
            "previousScore": self.previous_score,
            "change": round(self.change, 2),
            "reasons": self.reasons,
            "ruleHits": [h.to_dict() for h in self.rule_hits],
        }


def _aware(dt: Optional[datetime]) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Component scores
# ---------------------------------------------------------------------------

def score_rules(hits: Sequence[RuleHit]) -> tuple[float, list[RuleHit]]:
    """Sum rule contributions, deduplicated by rule id.

    Returns `(score, effective_hits)`. Deduplication is the mechanism behind
    property 1: a rule that fires repeatedly inside one window counts once, so
    hammering the same behaviour cannot push an employee to CRITICAL on volume
    alone. Genuinely different behaviour still accumulates, one rule at a time.
    """
    best: dict[str, RuleHit] = {}
    for hit in hits:
        current = best.get(hit.rule_id)
        if current is None or hit.risk > current.risk:
            best[hit.rule_id] = hit
    effective = list(best.values())
    total = sum(h.risk for h in effective)
    return min(100.0, total), effective


def score_ml(raw_ml: Optional[float], rule_score: float) -> float:
    """Apply the trust discount to a raw ML anomaly score (0–100).

    `raw_ml` is expected normalised to 0–100 by the caller. A score with no
    corroborating rule hits is halved — an outlier the rules cannot explain is
    a prompt to look, not a verdict.
    """
    if raw_ml is None:
        return 0.0
    value = max(0.0, min(100.0, float(raw_ml)))
    if rule_score < ML_TRUST_FLOOR:
        value *= ML_DISCOUNT
    return value


def combine(
    *,
    rule_score: float,
    ml_score: float,
    baseline_score: float,
    ml_available: bool = True,
) -> float:
    """Blend corroboration into the headroom above the rule score.

    The rule score is the base and is never scaled down: a window the
    deterministic rules have nothing to say about scores nothing, however
    unusual the statistics look. The ML and baseline signals fill the remaining
    headroom, capped at `SECONDARY_SHARE`, so they can only ever raise a score.

    Formulating this as a renormalised weighted average instead — the obvious
    first move — silently caps the achievable score whenever a component is
    absent, which for the ML model is *always* on a fresh install. See property
    3 in the module docstring.
    """
    components = [("baseline", baseline_score)]
    if ml_available:
        components.append(("ml", ml_score))

    weight_total = sum(SECONDARY_WEIGHTS[name] for name, _ in components)
    base = max(0.0, min(100.0, float(rule_score or 0.0)))
    if weight_total <= 0:
        return base

    corroboration = sum(SECONDARY_WEIGHTS[n] * float(v or 0.0) for n, v in components) / weight_total
    corroboration = max(0.0, min(100.0, corroboration))

    headroom = 100.0 - base
    return max(0.0, min(100.0, base + headroom * (corroboration / 100.0) * SECONDARY_SHARE))


def severity_floor(hits: Sequence[RuleHit]) -> float:
    """The minimum score implied by the most severe rule that fired.

    Reads the *set* of distinct rules, never their count, so it cannot be
    inflated by repeating one behaviour — property 1 is preserved.
    """
    return max((SEVERITY_FLOOR.get(h.severity, 0.0) for h in hits), default=0.0)


def decay(previous_score: Optional[float], elapsed: timedelta) -> float:
    """Exponential decay with a 24-hour half-life.

    Risk that never subsides is noise an analyst learns to ignore. Absent new
    signals an employee's score falls away on its own.
    """
    if not previous_score or previous_score <= 0:
        return 0.0
    hours = max(0.0, elapsed.total_seconds() / 3600.0)
    return previous_score * (0.5 ** (hours / DECAY_HALF_LIFE_HOURS))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def latest_risk_score(db: Session, employee_id) -> Optional[RiskScore]:
    return (
        db.query(RiskScore)
        .filter(RiskScore.employee_id == employee_id)
        .order_by(RiskScore.timestamp.desc())
        .first()
    )


def build_reasons(
    hits: Sequence[RuleHit],
    *,
    ml_score: float,
    baseline_score: float,
    ml_available: bool = True,
) -> list[str]:
    """Assemble the human-readable 'why' list, most serious first."""
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranked = sorted(hits, key=lambda h: (order.get(h.severity, 9), -h.risk))

    reasons = [f"[{h.rule_id}] {h.explanation}" for h in ranked]

    if ml_available and ml_score > 0:
        if ml_score >= 60:
            reasons.append(
                f"Machine-learning model flags this activity pattern as a strong "
                f"outlier against the organisation's normal behaviour "
                f"(anomaly score {ml_score:.0f}/100)."
            )
        elif ml_score >= 30:
            reasons.append(
                f"Activity is mildly unusual compared with peer behaviour "
                f"(anomaly score {ml_score:.0f}/100)."
            )

    if baseline_score >= 50:
        reasons.append(
            f"Activity volumes deviate substantially from this employee's own "
            f"established baseline (deviation {baseline_score:.0f}/100)."
        )
    elif baseline_score >= 25:
        reasons.append(
            f"Activity volumes sit above this employee's established baseline "
            f"(deviation {baseline_score:.0f}/100)."
        )

    if not reasons:
        reasons.append("No detection rules fired and activity is consistent with this employee's baseline.")
    return reasons[:MAX_REASONS]


def assess(
    db: Session,
    *,
    employee_id,
    rule_hits: Sequence[RuleHit],
    ml_score_raw: Optional[float] = None,
    ml_available: bool = True,
    baseline_score: float = 0.0,
    now: Optional[datetime] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    note: Optional[str] = None,
    persist: bool = True,
) -> RiskAssessment:
    """Assess one employee and (by default) append the result to `risk_scores`."""
    now = now or datetime.now(timezone.utc)

    rule_score, effective_hits = score_rules(rule_hits)
    ml_score = score_ml(ml_score_raw, rule_score) if ml_available else 0.0
    baseline_score = max(0.0, min(100.0, float(baseline_score or 0.0)))

    fresh = combine(
        rule_score=rule_score,
        ml_score=ml_score,
        baseline_score=baseline_score,
        ml_available=ml_available,
    )
    # A CRITICAL finding is a CRITICAL finding however quiet the statistics are
    # around it — see property 4.
    floor = severity_floor(effective_hits)
    fresh = max(fresh, floor)

    previous = latest_risk_score(db, employee_id)
    previous_score = previous.current_score if previous else None
    carry = decay(previous_score, now - _aware(previous.timestamp)) if previous else 0.0

    # Property 1, second half: risk never compounds. The score is the larger of
    # what is happening now and what is still decaying from before.
    score = round(max(fresh, carry), 2)
    level = level_for_score(score)
    change = round(score - (previous_score or 0.0), 2)

    reasons = build_reasons(
        effective_hits, ml_score=ml_score, baseline_score=baseline_score, ml_available=ml_available
    )

    assessment = RiskAssessment(
        score=score,
        level=level,
        rule_score=rule_score,
        ml_score=ml_score,
        baseline_score=baseline_score,
        previous_score=previous_score,
        change=change,
        reasons=reasons,
        rule_hits=effective_hits,
    )

    if persist:
        row = RiskScore(
            employee_id=employee_id,
            current_score=assessment.score,
            previous_score=previous_score,
            change=change,
            risk_level=level,
            reasons=reasons,
            rule_score=rule_score,
            ml_score=ml_score,
            baseline_score=baseline_score,
            window_start=window_start or (now - timedelta(hours=24)),
            window_end=window_end or now,
            timestamp=now,
            note=note,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return assessment
