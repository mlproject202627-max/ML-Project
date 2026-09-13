"""
Sentinel UEBA - Rule-Based Detection Engine

Deterministic rules that complement ML-based detection.
Each rule maps behavioural signals to Sentinel detection types.
"""
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger("sentinel.rules")


class RuleEngine:
    """
    Rule-based detection engine.

    Each rule evaluates a specific detection type and returns
    a signal if the rule fires.
    """

    def evaluate(self, features: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Evaluate all rules against the given features.

        Returns list of triggered signals:
        [
            {
                "type": "DETECTION_TYPE",
                "signal_value": float (0-1),
                "weight": float,
                "description": str,
                "rule_fired": str
            }
        ]
        """
        signals = []

        # Rule 1: Off-hours access
        sig = self._rule_off_hours(features)
        if sig:
            signals.append(sig)

        # Rule 2: Dormant account revival
        sig = self._rule_dormant_account(features)
        if sig:
            signals.append(sig)

        # Rule 3: Privilege escalation
        sig = self._rule_privilege_escalation(features)
        if sig:
            signals.append(sig)

        # Rule 4: Resource snooping
        sig = self._rule_resource_snooping(features)
        if sig:
            signals.append(sig)

        # Rule 5: Peer deviation
        sig = self._rule_peer_deviation(features)
        if sig:
            signals.append(sig)

        # Rule 6: Session anomaly
        sig = self._rule_session_anomaly(features)
        if sig:
            signals.append(sig)

        # Rule 7: Impossible travel (via unusual location)
        sig = self._rule_impossible_travel(features)
        if sig:
            signals.append(sig)

        # Rule 8: Lateral movement (via access velocity + privilege)
        sig = self._rule_lateral_movement(features)
        if sig:
            signals.append(sig)

        return signals

    def _rule_off_hours(self, f: Dict) -> Optional[Dict]:
        """Detect access outside normal working hours."""
        off_hours = f.get("off_hours_ratio", 0)
        weekend = f.get("weekend_ratio", 0)
        after_hours_sensitive = f.get("after_hours_sensitive_access", 0)

        if off_hours > 0.4 or (off_hours > 0.25 and after_hours_sensitive > 2):
            score = min(1.0, off_hours * 1.2 + (after_hours_sensitive * 0.05))
            return {
                "type": "OFF_HOURS_ACCESS",
                "signal_value": round(score, 3),
                "weight": 0.20,
                "description": f"Off-hours access ratio: {off_hours:.0%}, after-hours sensitive: {after_hours_sensitive}",
                "rule_fired": f"off_hours_ratio={off_hours:.3f} > 0.40",
            }
        return None

    def _rule_dormant_account(self, f: Dict) -> Optional[Dict]:
        """Detect dormant account revival."""
        dormant = f.get("dormant_account_days", 0)
        velocity = f.get("access_velocity_per_hour", 0)

        if dormant > 30 and velocity > 10:
            score = min(1.0, (dormant / 90) * 0.7 + (velocity / 30) * 0.3)
            return {
                "type": "DORMANT_ACCOUNT_REVIVAL",
                "signal_value": round(score, 3),
                "weight": 0.15,
                "description": f"Account dormant for {dormant} days, now accessing at {velocity} events/hour",
                "rule_fired": f"dormant_account_days={dormant} > 30 AND velocity={velocity} > 10",
            }
        return None

    def _rule_privilege_escalation(self, f: Dict) -> Optional[Dict]:
        """Detect privilege escalation."""
        priv_count = f.get("privileged_access_count", 0)
        priv_changes = f.get("privilege_change_count_30d", 0)
        account_type = f.get("account_type", "standard")

        if priv_changes > 2 or (priv_count > 20 and account_type != "privileged"):
            score = min(1.0, (priv_changes / 8) * 0.6 + (priv_count / 40) * 0.4)
            return {
                "type": "PRIVILEGE_ESCALATION",
                "signal_value": round(score, 3),
                "weight": 0.18,
                "description": f"Privilege changes: {priv_changes}/30d, privileged access count: {priv_count}",
                "rule_fired": f"privilege_change_count_30d={priv_changes} > 2",
            }
        return None

    def _rule_resource_snooping(self, f: Dict) -> Optional[Dict]:
        """Detect resource snooping / excessive access."""
        sensitive = f.get("sensitive_file_access", 0)
        ext_transfer = f.get("external_transfer_mb", 0)
        cloud_upload = f.get("cloud_upload_mb", 0)

        if sensitive > 8 or ext_transfer > 80 or cloud_upload > 50:
            score = min(1.0, (sensitive / 20) * 0.4 + (ext_transfer / 200) * 0.3 + (cloud_upload / 100) * 0.3)
            return {
                "type": "RESOURCE_SNOOPING",
                "signal_value": round(score, 3),
                "weight": 0.12,
                "description": f"Sensitive files: {sensitive}, external transfer: {ext_transfer}MB, cloud upload: {cloud_upload}MB",
                "rule_fired": f"sensitive_file_access={sensitive} > 8 OR ext_transfer={ext_transfer} > 80",
            }
        return None

    def _rule_peer_deviation(self, f: Dict) -> Optional[Dict]:
        """Detect peer-group deviation."""
        peer_dev = f.get("peer_deviation_score", 0)

        if peer_dev > 0.5:
            score = min(1.0, peer_dev * 1.3)
            return {
                "type": "PEER_GROUP_DEVIATION",
                "signal_value": round(score, 3),
                "weight": 0.15,
                "description": f"Peer deviation score: {peer_dev:.3f}",
                "rule_fired": f"peer_deviation_score={peer_dev:.3f} > 0.50",
            }
        return None

    def _rule_session_anomaly(self, f: Dict) -> Optional[Dict]:
        """Detect session anomalies."""
        duration = f.get("session_duration_mean_min", 0)
        remote = f.get("remote_session_ratio", 0)
        velocity = f.get("access_velocity_per_hour", 0)

        if (duration > 120 and remote > 0.7) or velocity > 30:
            score = min(1.0, (duration / 200) * 0.4 + remote * 0.3 + (velocity / 50) * 0.3)
            return {
                "type": "SESSION_ANOMALY",
                "signal_value": round(score, 3),
                "weight": 0.10,
                "description": f"Mean session: {duration:.0f}min, remote: {remote:.0%}, velocity: {velocity}/hr",
                "rule_fired": f"session_duration={duration} > 120 AND remote={remote} > 0.7",
            }
        return None

    def _rule_impossible_travel(self, f: Dict) -> Optional[Dict]:
        """Detect impossible travel (via unusual location score)."""
        unusual_loc = f.get("unusual_location_score", 0)

        if unusual_loc > 0.6:
            score = min(1.0, unusual_loc * 1.2)
            return {
                "type": "IMPOSSIBLE_TRAVEL",
                "signal_value": round(score, 3),
                "weight": 0.15,
                "description": f"Unusual location score: {unusual_loc:.3f}",
                "rule_fired": f"unusual_location_score={unusual_loc:.3f} > 0.60",
            }
        return None

    def _rule_lateral_movement(self, f: Dict) -> Optional[Dict]:
        """Detect lateral movement indicators."""
        velocity = f.get("access_velocity_per_hour", 0)
        priv_count = f.get("privileged_access_count", 0)
        remote = f.get("remote_session_ratio", 0)

        if velocity > 25 and priv_count > 15:
            score = min(1.0, (velocity / 40) * 0.5 + (priv_count / 40) * 0.5)
            return {
                "type": "LATERAL_MOVEMENT",
                "signal_value": round(score, 3),
                "weight": 0.18,
                "description": f"High access velocity ({velocity}/hr) with elevated privilege use ({priv_count})",
                "rule_fired": f"velocity={velocity} > 25 AND privileged_access={priv_count} > 15",
            }
        return None


# Singleton
rule_engine = RuleEngine()
