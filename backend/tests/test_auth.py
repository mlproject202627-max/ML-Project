import pytest
from fastapi.testclient import TestClient


def test_login_success(client, test_user):
    """Test successful login."""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@sentinel.demo",
        "password": "TestPass123!"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["user"]["email"] == "test@sentinel.demo"


def test_login_wrong_password(client, test_user):
    """Test login with wrong password."""
    response = client.post("/api/v1/auth/login", json={
        "email": "test@sentinel.demo",
        "password": "WrongPassword"
    })
    
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@sentinel.demo",
        "password": "password"
    })
    
    assert response.status_code == 401


def test_get_me(client, auth_headers):
    """Test get current user."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@sentinel.demo"
    assert data["name"] == "Test User"


def test_get_me_unauthorized(client):
    """Test get current user without auth."""
    response = client.get("/api/v1/auth/me")
    
    assert response.status_code == 401  # HTTPBearer auto_error returns 401 when no credentials


def test_refresh_token(client, test_user):
    """Test token refresh."""
    # First login
    login_response = client.post("/api/v1/auth/login", json={
        "email": "test@sentinel.demo",
        "password": "TestPass123!"
    })
    refresh_token = login_response.json()["refreshToken"]
    
    # Refresh
    response = client.post("/api/v1/auth/refresh", json={
        "refreshToken": refresh_token
    })
    
    assert response.status_code == 200
    assert "accessToken" in response.json()


def test_refresh_invalid_token(client):
    """Test refresh with invalid token."""
    response = client.post("/api/v1/auth/refresh", json={
        "refreshToken": "invalid-token"
    })
    
    assert response.status_code == 401


def test_logout(client, auth_headers):
    """Test logout."""
    response = client.post("/api/v1/auth/logout", headers=auth_headers)
    
    assert response.status_code == 200
