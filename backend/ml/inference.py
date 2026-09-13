"""
Sentinel UEBA - Inference Service

Loads the trained pipeline and provides prediction interface.
"""
import numpy as np
import joblib
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

from ml.preprocess import NUMERIC_FEATURES, CATEGORICAL_FEATURES

logger = logging.getLogger("sentinel.ml")

ARTIFACTS_DIR = Path("ml/artifacts")
PIPELINE_PATH = ARTIFACTS_DIR / "sentinel_ueba_pipeline.joblib"


class MLService:
    """Singleton ML service that loads and serves predictions."""

    def __init__(self):
        self._pipeline = None
        self._loaded = False

    def load(self) -> bool:
        """Load the trained pipeline from disk."""
        if not PIPELINE_PATH.exists():
            logger.warning(f"Pipeline not found at {PIPELINE_PATH}")
            return False

        try:
            self._pipeline = joblib.load(PIPELINE_PATH)
            self._loaded = True
            logger.info(f"Loaded model: {self._pipeline['model_name']} v{self._pipeline['model_version']}")
            return True
        except Exception as e:
            logger.error(f"Failed to load pipeline: {e}")
            return False

    @property
    def is_ready(self) -> bool:
        return self._loaded and self._pipeline is not None

    @property
    def model_version(self) -> str:
        if self._pipeline:
            return self._pipeline.get("model_version", "unknown")
        return "not-loaded"

    @property
    def model_name(self) -> str:
        if self._pipeline:
            return self._pipeline.get("model_name", "unknown")
        return "not-loaded"

    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Run prediction on a single feature dict.

        Returns:
            {
                "anomaly_probability": float,
                "predicted_class": int,
                "confidence": float,
                "model_version": str,
                "risk_factors": [...]
            }
        """
        if not self.is_ready:
            raise RuntimeError("ML model not loaded")

        import pandas as pd

        # Build feature DataFrame
        all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        row = {}
        for col in all_features:
            row[col] = features.get(col, np.nan)

        df = pd.DataFrame([row])

        # Preprocess
        preprocessor = self._pipeline["preprocessor"]
        X = preprocessor.transform(df)

        # Predict
        model = self._pipeline["model"]
        proba = model.predict_proba(X)[0]
        anomaly_prob = float(proba[1])
        predicted_class = int(anomaly_prob >= 0.5)
        confidence = float(abs(proba[predicted_class] - 0.5) * 2)

        # Feature contributions
        risk_factors = self._compute_risk_factors(features, X)

        return {
            "anomaly_probability": round(anomaly_prob, 4),
            "predicted_class": predicted_class,
            "confidence": round(confidence, 4),
            "model_version": self._pipeline["model_version"],
            "risk_factors": risk_factors,
        }

    def _compute_risk_factors(self, features: Dict[str, Any], X_processed) -> List[Dict]:
        """Compute risk factor contributions for explainability."""
        importance = self._pipeline.get("feature_importance", [])

        factors = []
        for fname, imp in importance[:8]:
            value = features.get(fname, 0)
            if value is not None and imp > 0.01:
                factors.append({
                    "feature": fname,
                    "value": float(value) if isinstance(value, (int, float)) else str(value),
                    "contribution": round(float(imp), 4),
                    "description": self._describe_signal(fname, value),
                })

        return factors

    def _describe_signal(self, feature: str, value) -> str:
        """Generate human-readable description for a signal."""
        descriptions = {
            "off_hours_ratio": "After-hours activity",
            "peer_deviation_score": "Deviation from peer group behaviour",
            "privileged_access_count": "Privileged resource access",
            "sensitive_file_access": "Sensitive file access frequency",
            "external_transfer_mb": "External data transfer volume",
            "unusual_location_score": "Unusual geographic access pattern",
            "new_device_score": "Novel device usage",
            "failed_login_rate": "Failed authentication attempts",
            "dormant_account_days": "Account dormancy period",
            "cloud_upload_mb": "Cloud upload activity",
            "email_external_ratio": "External email communication ratio",
            "session_duration_mean_min": "Session duration patterns",
            "access_velocity_per_hour": "Access rate per hour",
            "remote_session_ratio": "Remote session proportion",
            "after_hours_sensitive_access": "After-hours sensitive resource access",
            "usb_event_count": "USB device events",
            "privilege_change_count_30d": "Recent privilege changes",
            "asset_criticality": "Asset criticality level",
            "login_count_7d": "Weekly login frequency",
            "weekend_ratio": "Weekend activity proportion",
        }
        return descriptions.get(feature, f"{feature}: {value}")


# Singleton
ml_service = MLService()
