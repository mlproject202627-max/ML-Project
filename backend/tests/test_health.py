import pytest
from fastapi.testclient import TestClient


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sentinel"
    assert data["version"] == "1.0.0"


def test_docs_available(client):
    """Test OpenAPI docs are available."""
    response = client.get("/docs")
    assert response.status_code == 200
