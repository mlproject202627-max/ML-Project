import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.user import User
from app.models.anomaly import Anomaly


def create_test_anomaly(db: Session, user_id) -> Anomaly:
    """Helper to create a test anomaly."""
    anomaly = Anomaly(
        user_id=user_id,
        detection_type="OFF_HOURS_ACCESS",
        severity="HIGH",
        risk_score=75.0,
        anomaly_score=0.75,
        confidence=0.85,
        description="Test anomaly",
        status="OPEN",
        detected_at=datetime.now(timezone.utc),
    )
    db.add(anomaly)
    db.commit()
    return anomaly


def test_list_anomalies(client, auth_headers, test_user, db_session):
    """Test listing anomalies."""
    # Create test anomaly
    create_test_anomaly(db_session, test_user.id)
    
    response = client.get("/api/v1/anomalies", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_get_anomaly_by_id(client, auth_headers, test_user, db_session):
    """Test getting anomaly by ID."""
    anomaly = create_test_anomaly(db_session, test_user.id)
    
    response = client.get(f"/api/v1/anomalies/{anomaly.id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["detection_type"] == "OFF_HOURS_ACCESS"
    assert data["severity"] == "HIGH"


def test_get_anomaly_not_found(client, auth_headers):
    """Test getting non-existent anomaly."""
    import uuid
    fake_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/anomalies/{fake_id}", headers=auth_headers)
    
    assert response.status_code == 404


def test_filter_anomalies_by_severity(client, auth_headers, test_user, db_session):
    """Test filtering anomalies by severity."""
    create_test_anomaly(db_session, test_user.id)
    
    response = client.get("/api/v1/anomalies?severity=HIGH", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["severity"] == "HIGH"


def test_filter_anomalies_by_status(client, auth_headers, test_user, db_session):
    """Test filtering anomalies by status."""
    create_test_anomaly(db_session, test_user.id)
    
    response = client.get("/api/v1/anomalies?status_filter=OPEN", headers=auth_headers)
    
    assert response.status_code == 200


def test_pagination(client, auth_headers, test_user, db_session):
    """Test pagination works."""
    for _ in range(5):
        create_test_anomaly(db_session, test_user.id)
    
    response = client.get("/api/v1/anomalies?page=1&page_size=2", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["page"] == 1
    assert data["page_size"] == 2
