from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_security_analyst, require_security_read
from app.models.user import User

router = APIRouter(prefix="/api/v1/ml", tags=["ML Prediction"])


class PredictionRequest(BaseModel):
    features: Dict[str, Any]


class RiskFactorResponse(BaseModel):
    feature: str
    value: Any
    contribution: float
    description: Optional[str] = None


class PredictionResponse(BaseModel):
    predicted_class: int
    anomaly_probability: float
    risk_score: float
    severity: str
    confidence: float
    model_version: str
    risk_factors: List[RiskFactorResponse]
    rule_signals: List[Dict[str, Any]]
    explanation: str


@router.post("/predict", response_model=PredictionResponse)
def predict(
    request: PredictionRequest,
    current_user: User = Depends(require_security_analyst),
):
    """Run ML prediction on provided features."""
    from ml.inference import ml_service
    from ml.risk_engine import risk_engine
    from ml.rules import rule_engine

    if not ml_service.is_ready:
        raise HTTPException(
            status_code=503,
            detail="ML model not loaded. Run training first."
        )

    # Run ML prediction
    try:
        ml_result = ml_service.predict(request.features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

    # Run rule engine
    rule_signals = rule_engine.evaluate(request.features)

    # Compute risk score
    risk_result = risk_engine.compute_risk_score(ml_result, request.features)

    return PredictionResponse(
        predicted_class=ml_result["predicted_class"],
        anomaly_probability=ml_result["anomaly_probability"],
        risk_score=risk_result["risk_score"],
        severity=risk_result["severity"],
        confidence=ml_result["confidence"],
        model_version=ml_result["model_version"],
        risk_factors=[
            RiskFactorResponse(
                feature=f["feature"],
                value=f["value"],
                contribution=f["contribution"],
                description=f.get("description"),
            )
            for f in ml_result["risk_factors"]
        ],
        rule_signals=rule_signals,
        explanation=risk_result["explanation"],
    )


@router.get("/status")
def ml_status(
    current_user: User = Depends(require_security_read),
):
    """Operational status of the detector that actually scores risk.

    Console-gated (spec §22): model identity and training state are internals of
    the detection stack, not something an employee-portal session should be able
    to enumerate. Read-only, so VIEWER may see it; `/predict` above is a compute
    action and stays analyst-only.

    This reports `ml.anomaly` — the Isolation Forest wired into the risk engine
    through `services.detection`. The `ml.inference` service used by the
    `/predict` endpoint above is a legacy stub with fixed weights, retained for
    the ingestion path; reporting *its* version here told an operator about a
    model that plays no part in any alert.
    """
    from ml.anomaly import get_detector

    detector = get_detector()
    return {
        "loaded": detector is not None,
        "modelName": "IsolationForest",
        "trainingRows": detector.training_rows if detector else 0,
        "trainedAt": detector.trained_at.isoformat() if detector and detector.trained_at else None,
    }
