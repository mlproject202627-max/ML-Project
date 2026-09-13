"""
Sentinel UEBA - Risk Scoring Engine

Converts ML probability + contextual signals into a normalized 0-100 risk score.
Documents the calculation clearly.
"""
from typing import Dict, List, Any
import logging

logger = logging.getLogger("sentinel.risk")


class RiskEngine:
    """
    Risk Score Calculation:

    The risk score is a weighted combination of:
    1. ML model probability (40% weight)
    2. Behavioural signal severity (30% weight)
    3. Asset criticality (15% weight)
    4. Privilege context (15% weight)

    Final score is normalized to 0-100.

    Severity mapping:
        0-39:  LOW
        40-69: MEDIUM
        70-89: HIGH
        90-100: CRITICAL
    """

    # Severity thresholds (configurable)
    SEVERITY_THRESHOLDS = {
        "LOW": 0,
        "MEDIUM": 40,
        "HIGH": 70,
        "CRITICAL": 90,
    }

    # Weights for score components
    WEIGHTS = {
        "ml_probability": 0.40,
        "behavioural_signals": 0.30,
        "asset_criticality": 0.15,
        "privilege_context": 0.15,
    }

    def compute_risk_score(
        self,
        ml_prediction: Dict[str, Any],
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute risk score from ML prediction and contextual features.

        Args:
            ml_prediction: Output from MLService.predict()
            features: Original feature dict

        Returns:
            {
                "risk_score": float (0-100),
                "severity": str,
                "components": {...},
                "explanation": str
            }
        """
        ml_prob = ml_prediction.get("anomaly_probability", 0)
        risk_factors = ml_prediction.get("risk_factors", [])

        # Component 1: ML probability contribution (0-100)
        ml_component = ml_prob * 100

        # Component 2: Behavioural signal severity
        behavioural_score = self._compute_behavioural_score(features)
        behavioural_component = behavioural_score * 100

        # Component 3: Asset criticality (1-5 scale → 0-100)
        asset_criticality = features.get("asset_criticality", 1)
        asset_component = ((asset_criticality - 1) / 4) * 100

        # Component 4: Privilege context
        privilege_score = self._compute_privilege_score(features)
        privilege_component = privilege_score * 100

        # Weighted combination
        risk_score = (
            self.WEIGHTS["ml_probability"] * ml_component +
            self.WEIGHTS["behavioural_signals"] * behavioural_component +
            self.WEIGHTS["asset_criticality"] * asset_component +
            self.WEIGHTS["privilege_context"] * privilege_component
        )

        risk_score = max(0.0, min(100.0, round(risk_score, 1)))

        # Determine severity
        severity = self._score_to_severity(risk_score)

        # Generate explanation
        explanation = self._generate_explanation(
            risk_score, severity, ml_prob, features, risk_factors
        )

        return {
            "risk_score": risk_score,
            "severity": severity,
            "components": {
                "ml_probability": round(ml_component, 1),
                "behavioural_signals": round(behavioural_component, 1),
                "asset_criticality": round(asset_component, 1),
                "privilege_context": round(privilege_component, 1),
            },
            "weights": self.WEIGHTS,
            "explanation": explanation,
        }

    def _compute_behavioural_score(self, features: Dict[str, Any]) -> float:
        """Compute behavioural signal severity (0-1)."""
        signals = []

        # Off-hours activity
        off_hours = features.get("off_hours_ratio", 0)
        if off_hours > 0.5:
            signals.append(off_hours)

        # Peer deviation
        peer_dev = features.get("peer_deviation_score", 0)
        if peer_dev > 0.5:
            signals.append(peer_dev)

        # Unusual location
        unusual_loc = features.get("unusual_location_score", 0)
        if unusual_loc > 0.5:
            signals.append(unusual_loc)

        # New device
        new_device = features.get("new_device_score", 0)
        if new_device > 0.5:
            signals.append(new_device)

        # Failed login rate
        failed = features.get("failed_login_rate", 0)
        if failed > 0.3:
            signals.append(min(1.0, failed * 2))

        # Dormant account
        dormant = features.get("dormant_account_days", 0)
        if dormant > 30:
            signals.append(min(1.0, dormant / 120))

        # Sensitive file access
        sensitive = features.get("sensitive_file_access", 0)
        if sensitive > 5:
            signals.append(min(1.0, sensitive / 30))

        # External transfer
        ext_transfer = features.get("external_transfer_mb", 0)
        if ext_transfer > 50:
            signals.append(min(1.0, ext_transfer / 200))

        if not signals:
            return 0.0

        # Average of triggered signals
        return sum(signals) / len(signals)

    def _compute_privilege_score(self, features: Dict[str, Any]) -> float:
        """Compute privilege context score (0-1)."""
        scores = []

        priv_count = features.get("privileged_access_count", 0)
        if priv_count > 10:
            scores.append(min(1.0, priv_count / 40))

        priv_changes = features.get("privilege_change_count_30d", 0)
        if priv_changes > 2:
            scores.append(min(1.0, priv_changes / 10))

        account_type = features.get("account_type", "standard")
        if account_type == "privileged":
            scores.append(0.6)
        elif account_type == "service":
            scores.append(0.4)

        if not scores:
            return 0.0

        return sum(scores) / len(scores)

    def _score_to_severity(self, score: float) -> str:
        """Map risk score to severity level."""
        if score >= self.SEVERITY_THRESHOLDS["CRITICAL"]:
            return "CRITICAL"
        elif score >= self.SEVERITY_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif score >= self.SEVERITY_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        return "LOW"

    def _generate_explanation(
        self,
        risk_score: float,
        severity: str,
        ml_prob: float,
        features: Dict[str, Any],
        risk_factors: List[Dict],
    ) -> str:
        """Generate human-readable risk explanation."""
        parts = []

        if ml_prob > 0.7:
            parts.append("The ML model identified high anomaly probability")
        elif ml_prob > 0.4:
            parts.append("The ML model detected moderate anomalous patterns")
        else:
            parts.append("The ML model found limited anomalous signals")

        off_hours = features.get("off_hours_ratio", 0)
        if off_hours > 0.5:
            parts.append("unusually high after-hours activity contributed to the risk score")

        peer_dev = features.get("peer_deviation_score", 0)
        if peer_dev > 0.6:
            parts.append("significant deviation from peer-group behaviour was detected")

        unusual_loc = features.get("unusual_location_score", 0)
        if unusual_loc > 0.5:
            parts.append("access from unusual locations increased the risk assessment")

        sensitive = features.get("sensitive_file_access", 0)
        if sensitive > 8:
            parts.append("elevated sensitive file access was observed")

        if not parts:
            parts.append("multiple behavioural signals contributed to the risk assessment")

        return ". ".join(parts) + "."


# Singleton
risk_engine = RiskEngine()
