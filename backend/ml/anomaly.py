"""Isolation Forest anomaly detection (spec §12).

Detects behavioural outliers without ever having seen a labelled insider. The
model is intentionally *one* of three signals feeding the risk engine — never
the verdict on its own.

Three engineering decisions worth stating:

- **Self-calibrating scores.** Isolation Forest's `decision_function` output has
  no absolute meaning. Scores here are converted to a robust z-score against
  the training distribution (median + MAD) and squashed through a logistic, so
  50 always means "exactly typical" and 90+ means "far outside the training
  population" regardless of contamination settings.
- **Absence is explicit, not zero.** With too little history to train, the
  detector reports `available=False`. The risk engine then blends over its
  remaining signals without lowering the score — "no model" is never treated as
  "no anomaly", and never as evidence of good behaviour either.
- **Explanations come from the training distribution.** Per-feature z-scores
  against the saved training statistics identify which behaviours are unusual.
  This is a claim the model can actually support; SHAP values from a forest
  fitted on unlabelled data would not be more truthful, only more elaborate.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from ml.features import FEATURE_LABELS, FEATURE_NAMES, FeatureVector

logger = logging.getLogger("sentinel.ml.anomaly")

#: Below this many training rows the model declines to make claims.
MIN_TRAINING_ROWS = 50

#: Where the trained artefact lives when `MODEL_PATH` is unset (spec §30).
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "isolation_forest.joblib"


def configured_model_path() -> Path:
    """The model artefact location, honouring the `MODEL_PATH` setting.

    Resolved per call rather than at import so tests and the demo can retrain
    into a temporary file without the module caching a stale location.
    """
    try:
        from app.core.config import settings

        configured = (settings.MODEL_PATH or "").strip()
    except Exception:  # configuration must never be why detection fails
        logger.warning("Could not read MODEL_PATH; using the default model location.")
        configured = ""
    return Path(configured) if configured else DEFAULT_MODEL_PATH

#: Logistic steepness: one robust sigma ≈ 27 points of score.
SIGMA_SCALE = 1.0


@dataclass
class AnomalyResult:
    """The detector's verdict on one feature vector."""

    score: float               # 0–100, 50 == typical
    available: bool
    is_outlier: bool
    contributions: list[dict]  # top features by |z| against training data
    model: str = "IsolationForest"

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 2),
            "available": self.available,
            "isOutlier": self.is_outlier,
            "model": self.model,
            "contributions": self.contributions,
        }


def _robust_stats(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Median and MAD-based sigma per column (MAD scaled to be std-consistent)."""
    median = np.median(matrix, axis=0)
    mad = np.median(np.abs(matrix - median), axis=0)
    sigma = 1.4826 * mad
    # A constant column has zero spread; treat it as uninformative rather than
    # dividing by zero.
    sigma[sigma < 1e-9] = 1.0
    return median, sigma


class IsolationForestDetector:
    """Thin, serialisable wrapper around sklearn's IsolationForest."""

    def __init__(
        self,
        model=None,
        median=None,
        sigma=None,
        raw_median: float | None = None,
        raw_sigma: float | None = None,
        trained_at=None,
        training_rows: int = 0,
    ):
        self.model = model
        self.median = median
        self.sigma = sigma
        # Calibration constants for the raw decision margin, measured on the
        # training population itself (see `score_matrix`).
        self.raw_median = raw_median
        self.raw_sigma = raw_sigma
        self.trained_at = trained_at
        self.training_rows = training_rows

    # -- properties --------------------------------------------------------

    @property
    def is_trained(self) -> bool:
        return (
            self.model is not None
            and self.median is not None
            and self.sigma is not None
            and self.raw_median is not None
            and self.raw_sigma is not None
        )

    # -- training ----------------------------------------------------------

    @classmethod
    def train(
        cls,
        matrix: Sequence[Sequence[float]],
        *,
        contamination: float | str = "auto",
        n_estimators: int = 200,
        random_state: int = 42,
    ) -> "IsolationForestDetector":
        """Fit on a matrix of employee-window vectors.

        `random_state` is fixed so a demo produces the same scores twice.
        """
        from sklearn.ensemble import IsolationForest

        X = np.asarray(matrix, dtype=float)
        if X.ndim != 2 or X.shape[0] < MIN_TRAINING_ROWS:
            raise ValueError(
                f"Isolation Forest needs at least {MIN_TRAINING_ROWS} rows to train; got "
                f"{X.shape[0] if X.ndim == 2 else 0}."
            )
        if X.shape[1] != len(FEATURE_NAMES):
            raise ValueError(
                f"Expected {len(FEATURE_NAMES)} features in the order of FEATURE_NAMES, got {X.shape[1]}."
            )

        model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
            n_jobs=-1,
        )
        model.fit(X)
        median, sigma = _robust_stats(X)

        # Measure the raw decision margin across the training population so
        # inference-time scores can be calibrated to it. Without this the
        # margin has no absolute meaning — its scale depends on n_estimators
        # and contamination.
        raw_train = -model.decision_function(X)
        raw_median = float(np.median(raw_train))
        raw_mad = float(np.median(np.abs(raw_train - raw_median)))
        raw_sigma = 1.4826 * raw_mad
        if raw_sigma < 1e-9:
            # Degenerate spread (near-identical training rows). Fall back to the
            # standard deviation so scoring stays monotonic.
            raw_sigma = float(np.std(raw_train)) or 1e-6

        logger.info("Trained Isolation Forest on %d rows × %d features", *X.shape)
        return cls(
            model=model,
            median=median,
            sigma=sigma,
            raw_median=raw_median,
            raw_sigma=raw_sigma,
            trained_at=datetime.now(timezone.utc),
            training_rows=int(X.shape[0]),
        )

    # -- inference ---------------------------------------------------------

    def _raw_anomaly(self, X: np.ndarray) -> np.ndarray:
        """Higher means more anomalous, 0 is the model's own decision boundary."""
        return -self.model.decision_function(X)

    def score_matrix(self, matrix: Sequence[Sequence[float]]) -> np.ndarray:
        """Return a 0–100 anomaly score per row (50 == median of training data)."""
        X = np.asarray(matrix, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        raw = self._raw_anomaly(X)

        # Calibrate the raw margin against the training population's own median
        # and MAD, giving a scale-free "how far out is this?" measure where 50
        # is exactly typical and each unit is one robust standard deviation.
        raw_sigma = float(self.raw_sigma) if self.raw_sigma else 1e-6
        z = (raw - float(self.raw_median or 0.0)) / max(raw_sigma, 1e-6)
        z = np.clip(z, -12.0, 12.0)
        scores = 100.0 / (1.0 + np.exp(-SIGMA_SCALE * z))
        return np.clip(scores, 0.0, 100.0)

    def score(self, vector: FeatureVector) -> AnomalyResult:
        if not self.is_trained:
            return AnomalyResult(score=0.0, available=False, is_outlier=False, contributions=[])
        X = np.asarray([vector.to_list()], dtype=float)
        value = float(self.score_matrix(X)[0])
        return AnomalyResult(
            score=value,
            available=True,
            is_outlier=bool(self.model.predict(X)[0] == -1),
            contributions=self.explain(vector),
        )

    def explain(self, vector: FeatureVector, limit: int = 5) -> list[dict]:
        """Features furthest from the training distribution, in robust sigmas."""
        if not self.is_trained:
            return []
        values = np.asarray(vector.to_list(), dtype=float)
        z = (values - self.median) / self.sigma

        ranked = sorted(
            ((abs(float(zi)), FEATURE_NAMES[i], float(values[i]), float(self.median[i]), float(zi))
             for i, zi in enumerate(z)),
            reverse=True,
        )
        out = []
        for magnitude, name, observed, typical, zi in ranked[:limit]:
            if magnitude < 1.0:
                break
            out.append({
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "value": round(observed, 2),
                "typical": round(typical, 2),
                "sigma": round(zi, 2),
                "direction": "above" if zi > 0 else "below",
            })
        return out

    # -- persistence -------------------------------------------------------

    def save(self, path: Optional[Path] = None) -> Path:
        import joblib

        path = Path(path or configured_model_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

        # A small sidecar so the model's provenance is inspectable without
        # unpickling it.
        meta = {
            "model": "IsolationForest",
            "featureNames": list(FEATURE_NAMES),
            "trainingRows": self.training_rows,
            "trainedAt": self.trained_at.isoformat() if self.trained_at else None,
        }
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        logger.info("Saved Isolation Forest to %s", path)
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> Optional["IsolationForestDetector"]:
        import joblib

        path = Path(path or configured_model_path())
        if not path.exists():
            return None
        try:
            detector = joblib.load(path)
        except Exception as exc:
            logger.warning("Could not load Isolation Forest from %s: %s", path, exc)
            return None
        return detector if isinstance(detector, cls) and detector.is_trained else None


# ---------------------------------------------------------------------------
# Process-wide instance
# ---------------------------------------------------------------------------

_detector: Optional[IsolationForestDetector] = None
_loaded = False


def get_detector(model_path: Optional[Path] = None, *, reload: bool = False) -> Optional[IsolationForestDetector]:
    """Lazily load the trained model. Returns None when no artefact exists."""
    global _detector, _loaded
    if _loaded and not reload:
        return _detector

    path = Path(model_path) if model_path else configured_model_path()
    _detector = IsolationForestDetector.load(path)
    _loaded = True
    if _detector is None:
        logger.info("No Isolation Forest artefact at %s — ML scoring disabled until trained.", path)
    return _detector


def reset_cache() -> None:
    """Drop the cached model (used by tests and after retraining)."""
    global _detector, _loaded
    _detector = None
    _loaded = False


def detect(vector: FeatureVector, *, model_path: Optional[Path] = None) -> AnomalyResult:
    """Score one vector. Reports `available=False` rather than guessing."""
    detector = get_detector(model_path)
    if detector is None:
        return AnomalyResult(score=0.0, available=False, is_outlier=False, contributions=[])
    return detector.score(vector)


# ---------------------------------------------------------------------------
# Training from telemetry
# ---------------------------------------------------------------------------

def build_training_matrix(
    db,
    *,
    days: int = 30,
    window_hours: int = 24,
    now: Optional[datetime] = None,
) -> tuple[list[list[float]], list[str]]:
    """Build one row per (employee, day) from stored telemetry.

    Returns `(matrix, row_labels)`. Training on each employee's *own* history
    is what makes the model sensitive to a teller's normal Tuesday rather than
    to a bank-wide average.
    """
    from app.models.activity import Activity
    from app.models.baseline import EmployeeBaseline
    from app.models.user import User

    from ml.features import extract_features, resource_department_map

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    rows: list[list[float]] = []
    labels: list[str] = []

    baselines = {str(b.employee_id): b for b in db.query(EmployeeBaseline).all()}
    employees = db.query(User).filter(User.status == "ACTIVE").all()

    for employee in employees:
        events = (
            db.query(Activity)
            .filter(Activity.user_id == employee.id, Activity.timestamp >= since, Activity.timestamp <= now)
            .order_by(Activity.timestamp.asc())
            .all()
        )
        if not events:
            continue

        dept_map = resource_department_map(db, events)
        baseline = baselines.get(str(employee.id))

        by_day: dict[str, list] = {}
        for event in events:
            ts = event.timestamp if event.timestamp.tzinfo else event.timestamp.replace(tzinfo=timezone.utc)
            by_day.setdefault(ts.date().isoformat(), []).append(event)

        for day, day_events in by_day.items():
            if len(day_events) < 3:
                # A two-event day carries no behavioural shape; including it
                # would teach the model that quiet days are outliers.
                continue
            vector = extract_features(day_events, baseline=baseline, resource_departments=dept_map)
            rows.append(vector.to_list())
            labels.append(f"{employee.employee_code or employee.email}:{day}")

    return rows, labels


def train_from_telemetry(
    db,
    *,
    days: int = 30,
    model_path: Optional[Path] = None,
) -> Optional[IsolationForestDetector]:
    """Fit and persist a model from whatever telemetry the database holds."""
    rows, labels = build_training_matrix(db, days=days)
    if len(rows) < MIN_TRAINING_ROWS:
        logger.warning(
            "Not enough telemetry to train (%d rows, need %d).", len(rows), MIN_TRAINING_ROWS
        )
        return None

    detector = IsolationForestDetector.train(rows)
    detector.save(model_path)
    reset_cache()
    detector = get_detector(model_path, reload=True)
    logger.info("Trained Isolation Forest on %d employee-days", len(labels))
    return detector
