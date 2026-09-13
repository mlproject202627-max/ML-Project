from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PredictionSignal:
    type: str
    contribution: float


@dataclass
class Prediction:
    user_id: str
    anomaly_score: float
    risk_score: float
    confidence: float
    detection_type: str
    signals: List[PredictionSignal]


class AnomalyDetector(ABC):
    """Abstract base class for anomaly detection models.
    
    Future implementations should override the predict method
    with actual ML model inference. This interface ensures the
    backend API does not need changes when the real model is added.
    """
    
    @abstractmethod
    def predict(self, features: dict) -> Prediction:
        """Predict anomaly for given features.
        
        Args:
            features: Dictionary of behavioral features
            
        Returns:
            Prediction with anomaly score, risk score, confidence, and signals
        """
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        pass
