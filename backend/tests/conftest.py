import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import Base, get_db
from app.core.security import hash_password, create_access_token
from app.models.user import User, Role, user_roles

TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide a clean database session for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    """Provide a test client."""
    return TestClient(app)


@pytest.fixture
def test_role(db_session):
    """Create a test role."""
    role = Role(name="SECURITY_ANALYST", description="Test role")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def test_user(db_session, test_role):
    """Create a test user."""
    user = User(
        name="Test User",
        email="test@sentinel.demo",
        password_hash=hash_password("TestPass123!"),
        department="Security",
        job_title="Analyst",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    
    db_session.execute(user_roles.insert().values(user_id=user.id, role_id=test_role.id))
    db_session.commit()
    
    return user


@pytest.fixture
def admin_role(db_session):
    """Create an admin role."""
    role = Role(name="ADMIN", description="Admin role")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def admin_user(db_session, admin_role):
    """Create an admin user."""
    user = User(
        name="Admin User",
        email="admin@sentinel.demo",
        password_hash=hash_password("AdminPass123!"),
        department="IT Ops",
        job_title="Administrator",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()
    
    db_session.execute(user_roles.insert().values(user_id=user.id, role_id=admin_role.id))
    db_session.commit()
    
    return user


@pytest.fixture
def analyst_token(test_user):
    """Generate an access token for the test user."""
    return create_access_token(data={"sub": str(test_user.id), "role": "SECURITY_ANALYST"})


@pytest.fixture
def admin_token(admin_user):
    """Generate an access token for the admin user."""
    return create_access_token(data={"sub": str(admin_user.id), "role": "ADMIN"})


@pytest.fixture
def auth_headers(analyst_token):
    """Provide authorization headers."""
    return {"Authorization": f"Bearer {analyst_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Provide admin authorization headers."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def viewer_role(db_session):
    """Create a read-only security role."""
    role = Role(name="VIEWER", description="Read-only security access")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def viewer_user(db_session, viewer_role):
    """Create a read-only security user."""
    user = User(
        name="Viewer User",
        email="viewer@sentinel.demo",
        password_hash=hash_password("ViewerPass123!"),
        department="Security",
        job_title="Compliance Reviewer",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()

    db_session.execute(user_roles.insert().values(user_id=user.id, role_id=viewer_role.id))
    db_session.commit()

    return user


@pytest.fixture
def viewer_headers(viewer_user):
    """Provide read-only security authorization headers."""
    token = create_access_token(data={"sub": str(viewer_user.id), "role": "VIEWER"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def teller_role(db_session):
    """Create a banking role — the *subject* of monitoring, not a monitor."""
    role = Role(name="TELLER", description="Branch counter operations")
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def teller_user(db_session, teller_role):
    """Create an employee-portal user."""
    user = User(
        name="Teller User",
        email="teller@sentinel.demo",
        password_hash=hash_password("TellerPass123!"),
        department="Retail Banking",
        job_title="Teller",
        status="ACTIVE",
    )
    db_session.add(user)
    db_session.commit()

    db_session.execute(user_roles.insert().values(user_id=user.id, role_id=teller_role.id))
    db_session.commit()

    return user


@pytest.fixture
def teller_headers(teller_user):
    """Provide employee-portal authorization headers."""
    token = create_access_token(data={"sub": str(teller_user.id), "role": "TELLER"})
    return {"Authorization": f"Bearer {token}"}
