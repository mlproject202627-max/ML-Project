"""QUARANTINED — do not use.

This module previously exported `detector = MockAnomalyDetector()`, which
returned `random.uniform(0.0, 1.0)` as an anomaly score, `random.choice` for a
detection type, and random per-signal contributions. It also reported
`is_ready() == True`.

That combination is a trap, not a convenience. `is_ready()` returning True meant
any code that adopted it would report itself operational while emitting pure
noise, and in a security system the failure mode of noise is not "no detection"
— it is alerts that name an employee, carry a risk score, and mean nothing.
Analysts who are shown enough of those stop reading the queue, which costs more
than having no queue at all.

It was never wired in: nothing in the application imported this module or
`app.ml.interface`. The real detector is `ml/anomaly.py`
(`IsolationForestDetector`), reached through `app.services.detection`.

The implementation is preserved in git history. Anything still reaching for
this module fails loudly here rather than silently producing numbers.
"""


class MockAnomalyDetector:  # pragma: no cover - retained only to fail loudly
    """Retained as a named error so an old import gives a clear message."""

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "MockAnomalyDetector has been removed. It returned random anomaly "
            "scores and reported itself ready. Use ml.anomaly.get_detector() — "
            "the Isolation Forest wired into the risk engine — or the rule "
            "engine alone, which needs no model. See docs/ml.md."
        )


def detector(*args, **kwargs):  # pragma: no cover - retained only to fail loudly
    """Formerly a module-level instance; now a call that refuses to exist."""
    raise RuntimeError(
        "app.ml.adapter.detector has been removed. See docs/ml.md for the "
        "detectors that actually score risk."
    )
