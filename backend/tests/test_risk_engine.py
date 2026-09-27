"""Risk engine tests (spec §11).

The four guarantees the module documents are each pinned by a test, because
they are the properties that keep the score meaningful rather than merely
large. Three of them exist because of a specific way the obvious implementation
is wrong, so each regression test names the failure it prevents.
"""
from datetime import timedelta

import pytest

from app.models.risk_score import level_for_score
from app.services import risk
from ml.rule_engine import RuleHit


def hit(rule_id, risk_value, severity="HIGH", name=None):
    return RuleHit(rule_id=rule_id, name=name or rule_id, severity=severity,
                   risk=risk_value, explanation=f"{rule_id} explanation")


# ---------------------------------------------------------------------------
# Bands (spec §11)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected", [
    (0, "LOW"), (20, "LOW"),
    (21, "MODERATE"), (40, "MODERATE"),
    (41, "ELEVATED"), (60, "ELEVATED"),
    (61, "HIGH"), (80, "HIGH"),
    (81, "CRITICAL"), (100, "CRITICAL"),
])
def test_risk_bands(score, expected):
    assert level_for_score(score) == expected


def test_level_clamps_out_of_range_scores():
    assert level_for_score(-5) == "LOW"
    assert level_for_score(999) == "CRITICAL"


# ---------------------------------------------------------------------------
# Guarantee 1 — repeated events cannot inflate risk
# ---------------------------------------------------------------------------

def test_repeated_identical_rule_counts_once():
    """Forty hits from one rule contribute exactly as much as one hit."""
    once = risk.score_rules([hit("RULE-004", 16.0)])
    forty = risk.score_rules([hit("RULE-004", 16.0) for _ in range(40)])
    assert once[0] == forty[0] == 16.0


def test_distinct_rules_still_accumulate():
    score, effective = risk.score_rules([hit("RULE-004", 16.0), hit("RULE-007", 22.0)])
    assert score == 38.0
    assert len(effective) == 2


def test_rule_score_is_capped_at_100():
    hits = [hit(f"RULE-{i:03d}", 40.0) for i in range(1, 6)]
    assert risk.score_rules(hits)[0] == 100.0


# ---------------------------------------------------------------------------
# Guarantee 2 — the ML model is never trusted on its own
# ---------------------------------------------------------------------------

def test_ml_score_is_halved_without_corroborating_rules():
    assert risk.score_ml(80.0, rule_score=0.0) == 40.0


def test_ml_score_is_kept_when_rules_corroborate():
    assert risk.score_ml(80.0, rule_score=risk.ML_TRUST_FLOOR) == 80.0


def test_ml_absent_scores_zero():
    assert risk.score_ml(None, rule_score=90.0) == 0.0


def test_ml_score_is_bounded():
    assert risk.score_ml(1e9, rule_score=90.0) == 100.0
    assert risk.score_ml(-10.0, rule_score=90.0) == 0.0


# ---------------------------------------------------------------------------
# Guarantee 3 — a missing signal does not lower the score
# ---------------------------------------------------------------------------

def test_missing_ml_does_not_lower_the_score():
    """Regression: renormalising a weighted average capped the score at 71/100.

    With no model trained — every fresh install — the ML component is absent.
    Scaling rules and baseline up into its weight looked harmless and was not:
    it put the CRITICAL band out of reach of the primary signal entirely.
    """
    with_ml = risk.combine(rule_score=100.0, ml_score=100.0, baseline_score=100.0, ml_available=True)
    without_ml = risk.combine(rule_score=100.0, ml_score=0.0, baseline_score=100.0, ml_available=False)
    assert with_ml == pytest.approx(100.0)
    assert without_ml == pytest.approx(100.0)


def test_rules_alone_can_reach_critical():
    """A maximal rule score must be able to reach the top band on its own."""
    assert risk.combine(rule_score=100.0, ml_score=0.0, baseline_score=0.0) == pytest.approx(100.0)


def test_rules_are_the_base_not_a_weighted_share():
    rules_only = risk.combine(rule_score=50.0, ml_score=0.0, baseline_score=0.0)
    baseline_only = risk.combine(rule_score=0.0, ml_score=0.0, baseline_score=50.0)
    assert rules_only == pytest.approx(50.0)
    assert rules_only > baseline_only


def test_corroboration_cannot_carry_a_score_on_its_own():
    """Perfect statistics with no rule hits stays inside the ELEVATED band."""
    perfect_statistics = risk.combine(rule_score=0.0, ml_score=100.0, baseline_score=100.0)
    assert perfect_statistics <= 50.0
    assert risk.level_for_score(perfect_statistics) == "ELEVATED"


# ---------------------------------------------------------------------------
# Guarantee 4 — the score cannot contradict the rule that produced it
# ---------------------------------------------------------------------------

def test_critical_rule_floors_the_score_at_high():
    """Regression: a lone CRITICAL rule scored 35/100 and raised no alert."""
    floor = risk.severity_floor([hit("RULE-009", 38.0, severity="CRITICAL")])
    assert floor == 61.0
    assert risk.level_for_score(floor) == "HIGH"


def test_high_rule_floors_the_score_at_elevated():
    floor = risk.severity_floor([hit("RULE-007", 22.0, severity="HIGH")])
    assert floor == 41.0
    assert risk.level_for_score(floor) == "ELEVATED"


def test_quiet_rules_do_not_floor():
    assert risk.severity_floor([]) == 0.0
    assert risk.severity_floor([hit("RULE-003", 12.0, severity="MEDIUM")]) == 0.0


def test_floor_is_not_inflated_by_repeating_a_rule():
    """Guarantee 1 still holds: the floor reads distinct rules, not their count."""
    hits = [hit("RULE-009", 38.0, severity="CRITICAL") for _ in range(50)]
    effective = risk.score_rules(hits)[1]
    assert risk.severity_floor(effective) == risk.severity_floor(effective[:1]) == 61.0


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------

def test_decay_halves_after_one_half_life():
    assert risk.decay(80.0, timedelta(hours=risk.DECAY_HALF_LIFE_HOURS)) == pytest.approx(40.0)


def test_decay_after_two_half_lives():
    assert risk.decay(80.0, timedelta(hours=2 * risk.DECAY_HALF_LIFE_HOURS)) == pytest.approx(20.0)


def test_decay_is_immediate_at_zero_elapsed():
    assert risk.decay(80.0, timedelta(0)) == pytest.approx(80.0)


def test_decay_of_nothing_is_zero():
    assert risk.decay(None, timedelta(hours=1)) == 0.0
    assert risk.decay(0.0, timedelta(hours=1)) == 0.0


# ---------------------------------------------------------------------------
# Reasons (spec §13 — readable by a non-ML administrator)
# ---------------------------------------------------------------------------

def test_reasons_lead_with_the_most_severe_rule():
    hits = [hit("RULE-003", 12.0, severity="MEDIUM"), hit("RULE-009", 38.0, severity="CRITICAL")]
    reasons = risk.build_reasons(hits, ml_score=0.0, baseline_score=0.0)
    assert reasons[0].startswith("[RULE-009]")


def test_reasons_are_plain_sentences_when_nothing_fired():
    reasons = risk.build_reasons([], ml_score=0.0, baseline_score=0.0)
    assert len(reasons) == 1
    assert "No detection rules fired" in reasons[0]


def test_reasons_mention_the_ml_score_only_when_notable():
    quiet = risk.build_reasons([], ml_score=10.0, baseline_score=0.0)
    assert not any("anomaly score" in r for r in quiet)

    loud = risk.build_reasons([], ml_score=75.0, baseline_score=0.0)
    assert any("anomaly score" in r for r in loud)


def test_reasons_are_capped():
    hits = [hit(f"RULE-{i:03d}", 5.0) for i in range(1, 12)]
    assert len(risk.build_reasons(hits, ml_score=90.0, baseline_score=90.0)) <= risk.MAX_REASONS
