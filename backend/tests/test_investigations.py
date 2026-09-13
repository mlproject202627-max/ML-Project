import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.user import User
from app.models.anomaly import Anomaly
from app.models.investigation import Investigation


def create_test_investigation(db: Session, anomaly_id, assigned_to=None) -> Investigation:
    """Helper to create a test investigation."""
    investigation = Investigation(
        anomaly_id=anomaly_id,
        assigned_to=assigned_to,
        title="Test Investigation",
        summary="Test summary",
        status="OPEN",
        priority="HIGH",
    )
    db.add(investigation)
    db.commit()
    return investigation


def create_test_anomaly_for_user(db: Session, user_id) -> Anomaly:
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


def test_create_investigation(client, auth_headers, test_user, db_session):
    """Test creating an investigation."""
    anomaly = create_test_anomaly_for_user(db_session, test_user.id)
    
    response = client.post("/api/v1/investigations", headers=auth_headers, json={
        "anomaly_id": str(anomaly.id),
        "title": "Test Investigation",
        "priority": "HIGH",
    })
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Investigation"
    assert data["status"] == "OPEN"


def test_list_investigations(client, auth_headers, test_user, db_session):
    """Test listing investigations."""
    anomaly = create_test_anomaly_for_user(db_session, test_user.id)
    create_test_investigation(db_session, anomaly.id)
    
    response = client.get("/api/v1/investigations", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


def test_get_investigation(client, auth_headers, test_user, db_session):
    """Test getting investigation by ID."""
    anomaly = create_test_anomaly_for_user(db_session, test_user.id)
    investigation = create_test_investigation(db_session, anomaly.id)
    
    response = client.get(f"/api/v1/investigations/{investigation.id}", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Investigation"


def test_resolve_investigation(client, auth_headers, test_user, db_session):
    """Test resolving an investigation."""
    anomaly = create_test_anomaly_for_user(db_session, test_user.id)
    investigation = create_test_investigation(db_session, anomaly.id)
    
    response = client.post(f"/api/v1/investigations/{investigation.id}/resolve", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESOLVED"
    assert data["resolved_at"] is not None
