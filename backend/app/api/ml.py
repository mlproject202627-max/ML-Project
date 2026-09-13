from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.dependencies import require_security_analyst
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
    current_user: User = Depends(get_current_user),
):
    """Get ML model status."""
    from ml.inference import ml_service

    return {
        "loaded": ml_service.is_ready,
        "model_name": ml_service.model_name,
        "model_version": ml_service.model_version,
    }
