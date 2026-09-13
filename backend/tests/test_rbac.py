import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password, create_access_token
from app.models.user import User, Role, user_roles


def create_user_with_role(db: Session, name: str, email: str, role_name: str) -> User:
    """Helper to create a user with a specific role."""
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.flush()
    
    user = User(
        name=name,
        email=email,
        password_hash=hash_password("TestPass123!"),
        department="Security",
        job_title="Test",
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    
    return user


def test_admin_access(client, db_session):
    """Test admin can access all endpoints."""
    admin = create_user_with_role(db_session, "Admin", "admin-rbac@test.com", "ADMIN")
    token = create_access_token(data={"sub": str(admin.id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/v1/users", headers=headers)
    assert response.status_code == 200


def test_viewer_cannot_modify_investigation(client, db_session):
    """Test viewer cannot modify investigations."""
    viewer = create_user_with_role(db_session, "Viewer", "viewer@test.com", "VIEWER")
    token = create_access_token(data={"sub": str(viewer.id), "role": "VIEWER"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/api/v1/investigations", headers=headers, json={
        "anomaly_id": "test-anomaly-id",
        "title": "Test Investigation",
    })
    assert response.status_code == 403


def test_analyst_can_view_anomalies(client, db_session):
    """Test analyst can view anomalies."""
    analyst = create_user_with_role(db_session, "Analyst", "analyst@test.com", "SECURITY_ANALYST")
    token = create_access_token(data={"sub": str(analyst.id), "role": "SECURITY_ANALYST"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/v1/anomalies", headers=headers)
    assert response.status_code == 200


def test_manager_can_manage_policies(client, db_session):
    """Test manager can manage policies."""
    manager = create_user_with_role(db_session, "Manager", "manager@test.com", "SECURITY_MANAGER")
    token = create_access_token(data={"sub": str(manager.id), "role": "SECURITY_MANAGER"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/api/v1/policies", headers=headers, json={
        "name": "Test Policy",
        "detection_type": "OFF_HOURS_ACCESS",
        "threshold": 0.7,
    })
    assert response.status_code == 201


def test_analyst_cannot_create_policy(client, db_session):
    """Test analyst cannot create policies."""
    analyst = create_user_with_role(db_session, "Analyst2", "analyst2@test.com", "SECURITY_ANALYST")
    token = create_access_token(data={"sub": str(analyst.id), "role": "SECURITY_ANALYST"})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/api/v1/policies", headers=headers, json={
        "name": "Test Policy",
        "detection_type": "OFF_HOURS_ACCESS",
        "threshold": 0.7,
    })
    assert response.status_code == 403
