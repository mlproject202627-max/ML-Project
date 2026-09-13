import pytest
from fastapi.testclient import TestClient


def test_dashboard_requires_auth(client):
    """Test dashboard requires authentication."""
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 403


def test_dashboard_returns_metrics(client, auth_headers):
    """Test dashboard returns metrics."""
    response = client.get("/api/v1/dashboard", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert "metrics" in data
    assert "anomalyTrend" in data
    assert "detectionMix" in data
    assert "priorityTriage" in data
    assert "behaviourDrift" in data
    
    metrics = data["metrics"]
    assert "openAlerts" in metrics
    assert "identitiesWatched" in metrics
    assert "anomaliesDetected" in metrics
    assert "meanRiskIndex" in metrics
    assert "watchlistCount" in metrics


def test_dashboard_anomaly_trend(client, auth_headers):
    """Test dashboard anomaly trend has 14 days."""
    response = client.get("/api/v1/dashboard", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["anomalyTrend"]) == 14
    for point in data["anomalyTrend"]:
        assert "label" in point
        assert "anomalies" in point
        assert "meanRisk" in point
