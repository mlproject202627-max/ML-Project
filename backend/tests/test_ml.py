import pytest
from ml.inference import ml_service
from ml.risk_engine import risk_engine
from ml.rules import rule_engine
from ml.preprocess import validate_schema, build_preprocessor, NUMERIC_FEATURES, CATEGORICAL_FEATURES
import pandas as pd
import numpy as np


@pytest.fixture(autouse=True)
def load_model():
    """Load ML model for tests."""
    if not ml_service.is_ready:
        ml_service.load()


def test_model_loads():
    """Test ML model loads successfully."""
    assert ml_service.is_ready
    assert ml_service.model_version == "sentinel-ueba-v1"


def test_prediction_returns_valid_structure():
    """Test prediction returns expected structure."""
    features = {
        "login_count_7d": 15,
        "failed_login_rate": 0.05,
        "off_hours_ratio": 0.3,
        "weekend_ratio": 0.1,
        "sensitive_file_access": 3,
        "external_transfer_mb": 10,
        "cloud_upload_mb": 5,
        "usb_event_count": 1,
        "privileged_access_count": 5,
        "privilege_change_count_30d": 0,
        "email_external_ratio": 0.2,
        "session_duration_mean_min": 45,
        "access_velocity_per_hour": 8,
        "remote_session_ratio": 0.3,
        "unusual_location_score": 0.2,
        "new_device_score": 0.1,
        "peer_deviation_score": 0.2,
        "dormant_account_days": 0,
        "after_hours_sensitive_access": 1,
        "asset_criticality": 2,
        "department": "Engineering",
        "role": "Engineer",
        "account_type": "standard",
    }

    result = ml_service.predict(features)

    assert "anomaly_probability" in result
    assert "predicted_class" in result
    assert "confidence" in result
    assert "model_version" in result
    assert "risk_factors" in result
    assert 0 <= result["anomaly_probability"] <= 1
    assert result["predicted_class"] in [0, 1]
    assert 0 <= result["confidence"] <= 1


def test_risk_engine_score_range():
    """Test risk engine produces score in 0-100."""
    features = {
        "off_hours_ratio": 0.8,
        "peer_deviation_score": 0.7,
        "unusual_location_score": 0.6,
        "asset_criticality": 4,
        "privileged_access_count": 20,
        "privilege_change_count_30d": 5,
        "account_type": "privileged",
    }

    ml_pred = {
        "anomaly_probability": 0.85,
        "risk_factors": [],
    }

    result = risk_engine.compute_risk_score(ml_pred, features)

    assert 0 <= result["risk_score"] <= 100
    assert result["severity"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert "explanation" in result
    assert "components" in result


def test_rule_engine_detects_off_hours():
    """Test rule engine fires off-hours rule."""
    features = {
        "off_hours_ratio": 0.7,
        "weekend_ratio": 0.2,
        "after_hours_sensitive_access": 5,
        "privileged_access_count": 3,
        "privilege_change_count_30d": 0,
        "sensitive_file_access": 2,
        "external_transfer_mb": 10,
        "cloud_upload_mb": 5,
        "dormant_account_days": 0,
        "peer_deviation_score": 0.3,
        "session_duration_mean_min": 45,
        "remote_session_ratio": 0.3,
        "access_velocity_per_hour": 8,
        "unusual_location_score": 0.2,
        "account_type": "standard",
    }

    signals = rule_engine.evaluate(features)
    types = [s["type"] for s in signals]
    assert "OFF_HOURS_ACCESS" in types


def test_rule_engine_detects_dormant_account():
    """Test rule engine fires dormant account rule."""
    features = {
        "off_hours_ratio": 0.2,
        "weekend_ratio": 0.1,
        "after_hours_sensitive_access": 0,
        "privileged_access_count": 3,
        "privilege_change_count_30d": 0,
        "sensitive_file_access": 2,
        "external_transfer_mb": 10,
        "cloud_upload_mb": 5,
        "dormant_account_days": 60,
        "peer_deviation_score": 0.2,
        "session_duration_mean_min": 45,
        "remote_session_ratio": 0.3,
        "access_velocity_per_hour": 15,
        "unusual_location_score": 0.2,
        "account_type": "standard",
    }

    signals = rule_engine.evaluate(features)
    types = [s["type"] for s in signals]
    assert "DORMANT_ACCOUNT_REVIVAL" in types


def test_schema_validation_catches_missing():
    """Test schema validation catches missing columns."""
    df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
    errors = validate_schema(df)
    assert len(errors) > 0
    assert any("insider_threat" in e for e in errors)


def test_preprocessing_pipeline():
    """Test preprocessing pipeline builds correctly."""
    preprocessor = build_preprocessor()
    assert preprocessor is not None

    # Create sample data
    sample = pd.DataFrame({
        "login_count_7d": [10, 20],
        "failed_login_rate": [0.1, 0.2],
        "off_hours_ratio": [0.3, 0.5],
        "weekend_ratio": [0.1, 0.2],
        "sensitive_file_access": [5, 10],
        "external_transfer_mb": [20, 50],
        "cloud_upload_mb": [10, 30],
        "usb_event_count": [1, 3],
        "privileged_access_count": [5, 15],
        "privilege_change_count_30d": [0, 2],
        "email_external_ratio": [0.2, 0.4],
        "session_duration_mean_min": [45, 90],
        "access_velocity_per_hour": [8, 20],
        "remote_session_ratio": [0.3, 0.6],
        "unusual_location_score": [0.2, 0.5],
        "new_device_score": [0.1, 0.3],
        "peer_deviation_score": [0.2, 0.6],
        "dormant_account_days": [0, 30],
        "after_hours_sensitive_access": [1, 5],
        "asset_criticality": [2, 4],
        "department": ["Engineering", "Finance"],
        "role": ["Engineer", "Analyst"],
        "account_type": ["standard", "privileged"],
    })

    X_processed = preprocessor.fit_transform(sample)
    assert X_processed.shape[0] == 2
    assert X_processed.shape[1] > len(NUMERIC_FEATURES)  # More cols after one-hot


def test_invalid_features_handled():
    """Test prediction handles missing/invalid features gracefully."""
    features = {}  # Empty features
    result = ml_service.predict(features)
    assert "anomaly_probability" in result
    assert 0 <= result["anomaly_probability"] <= 1
