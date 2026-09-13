import random
from typing import List
from app.ml.interface import AnomalyDetector, Prediction, PredictionSignal


class MockAnomalyDetector(AnomalyDetector):
    """Mock anomaly detector for development and testing.
    
    Returns random predictions. Replace with actual ML model
    for production use.
    """
    
    DETECTION_TYPES = [
        "OFF_HOURS_ACCESS",
        "LATERAL_MOVEMENT",
        "DORMANT_ACCOUNT_REVIVAL",
        "RESOURCE_SNOOPING",
        "PRIVILEGE_ESCALATION",
        "IMPOSSIBLE_TRAVEL",
        "PEER_GROUP_DEVIATION",
        "SESSION_ANOMALY",
    ]
    
    SIGNAL_TYPES = [
        "OFF_HOURS_ACCESS",
        "PEER_GROUP_DEVIATION",
        "PRIVILEGE_ESCALATION",
        "RESOURCE_ACCESS",
        "LOCATION_ANOMALY",
        "SESSION_BEHAVIOR",
    ]
    
    def predict(self, features: dict) -> Prediction:
        """Generate a mock prediction."""
        anomaly_score = round(random.uniform(0.0, 1.0), 3)
        risk_score = round(anomaly_score * 100, 1)
        confidence = round(random.uniform(0.5, 0.99), 2)
        detection_type = random.choice(self.DETECTION_TYPES)
        
        # Generate 2-4 random signals
        num_signals = random.randint(2, 4)
        remaining_weight = 1.0
        signals = []
        
        for i in range(num_signals):
            if i == num_signals - 1:
                weight = remaining_weight
            else:
                weight = round(random.uniform(0.1, remaining_weight / 2), 2)
                remaining_weight -= weight
            
            signals.append(PredictionSignal(
                type=random.choice(self.SIGNAL_TYPES),
                contribution=round(weight * anomaly_score, 3),
            ))
        
        return Prediction(
            user_id=features.get("user_id", "unknown"),
            anomaly_score=anomaly_score,
            risk_score=risk_score,
            confidence=confidence,
            detection_type=detection_type,
            signals=signals,
        )
    
    def is_ready(self) -> bool:
        return True


# Global instance
detector = MockAnomalyDetector()
