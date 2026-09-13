from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.activity import Activity
from app.models.risk_event import RiskEvent


# Default weights for risk signals
DEFAULT_WEIGHTS = {
    "OFF_HOURS_ACCESS": 0.20,
    "LATERAL_MOVEMENT": 0.18,
    "PRIVILEGE_ESCALATION": 0.17,
    "IMPOSSIBLE_TRAVEL": 0.15,
    "PEER_GROUP_DEVIATION": 0.12,
    "RESOURCE_SNOOPING": 0.08,
    "SESSION_ANOMALY": 0.05,
    "DORMANT_ACCOUNT_REVIVAL": 0.05,
}


class RiskService:
    """Centralized risk scoring service.
    
    Computes user risk scores from behavioral signals.
    All risk calculations should go through this service
    to maintain consistency and explainability.
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS
    
    def compute_risk_score(self, signals: List[Dict]) -> float:
        """Compute a normalized risk score (0-100) from behavioral signals.
        
        Args:
            signals: List of signal dicts with 'type' and 'value' keys
            
        Returns:
            Risk score normalized to 0-100
        """
        if not signals:
            return 0.0
        
        total_contribution = 0.0
        total_weight = 0.0
        
        for signal in signals:
            signal_type = signal.get("type", "")
            signal_value = signal.get("value", 0.0)
            weight = self.weights.get(signal_type, 0.05)
            
            contribution = signal_value * weight
            total_contribution += contribution
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Normalize to 0-100
        normalized_score = (total_contribution / total_weight) * 100
        return min(100.0, max(0.0, round(normalized_score, 1)))
    
    def create_risk_events(
        self,
        db: Session,
        user_id: str,
        anomaly_id: Optional[str],
        signals: List[Dict],
    ) -> List[RiskEvent]:
        """Create risk event records for explainability.
        
        Args:
            db: Database session
            user_id: User ID
            anomaly_id: Optional anomaly ID
            signals: List of signal dicts
            
        Returns:
            List of created RiskEvent objects
        """
        risk_events = []
        
        for signal in signals:
            signal_type = signal.get("type", "")
            signal_value = signal.get("value", 0.0)
            weight = self.weights.get(signal_type, 0.05)
            contribution = signal_value * weight
            
            risk_event = RiskEvent(
                user_id=user_id,
                anomaly_id=anomaly_id,
                signal_type=signal_type,
                signal_value=signal_value,
                weight=weight,
                contribution=contribution,
            )
            db.add(risk_event)
            risk_events.append(risk_event)
        
        return risk_events


# Global instance
risk_service = RiskService()
