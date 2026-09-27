from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uuid
from contextlib import asynccontextmanager

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, Base, get_db
# Importing the package (not individual modules) is what guarantees every model
# is registered on `Base.metadata` before the startup `create_all` below.
import app.models  # noqa: F401
from app.models.activity import Activity
from app.models.baseline import EmployeeBaseline
from app.api import auth, users, dashboard, anomalies, investigations, activity, policies, notifications, ingestion
from app.api import ml, telemetry, banking
from app.api import resources, simulation, admin, alerts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sentinel")


# RBAC roles seeded at startup (idempotent) — Sentinel platform + banking roles (spec §2)
SYSTEM_ROLES = [
    ("ADMIN", "Full platform administration"),
    ("SECURITY_MANAGER", "Manage policies, investigations and assignments"),
    ("SECURITY_ANALYST", "Investigate alerts and run ML predictions"),
    ("VIEWER", "Read-only security dashboard access"),
    ("TELLER", "Branch counter operations: deposits, withdrawals, transfers"),
    ("RELATIONSHIP_MANAGER", "Customer relationships, KYC and service requests"),
    ("BRANCH_MANAGER", "Branch oversight, approvals and staff overview"),
    ("COMPLIANCE_OFFICER", "Review suspicious activity, KYC and audit records"),
    ("OPERATIONS_MANAGER", "Operational reports and transaction monitoring"),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    logger.info("Sentinel API starting up...")

    # Try to create tables (auto-migration for dev, not a replacement for Alembic)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.warning(f"Could not auto-create tables (DB may be unavailable): {e}")

    # Idempotent role bootstrap so newly added roles exist on running instances
    try:
        from app.core.database import SessionLocal
        from app.models.user import Role
        db = SessionLocal()
        try:
            for name, description in SYSTEM_ROLES:
                if not db.query(Role).filter(Role.name == name).first():
                    db.add(Role(name=name, description=description))
            db.commit()
        finally:
            db.close()
        logger.info("System roles verified/seeded.")
    except Exception as e:
        logger.warning(f"Role bootstrap skipped: {e}")

    # Load ML model
    logger.info("Loading ML model...")
    from ml.inference import ml_service
    if ml_service.load():
        logger.info(f"ML model loaded: {ml_service.model_name} v{ml_service.model_version}")
    else:
        logger.warning("ML model not found. Run 'python ml/train.py' first.")

    # Banking portal demo data (idempotent)
    try:
        from app.utils.seed_banking import seed as seed_banking
        seed_banking()
    except Exception as e:
        logger.warning(f"Banking seed skipped: {e}")

    # Classified resource registry (spec §5) — depends on branches/customers
    try:
        from app.utils.seed_resources import seed as seed_resources
        seed_resources()
    except Exception as e:
        logger.warning(f"Resource registry seed skipped: {e}")

    logger.info("Sentinel API is ready.")
    yield

    # Shutdown
    logger.info("Sentinel API shutting down...")
    engine.dispose()


app = FastAPI(
    title="Sentinel - Insider Threat Detection API",
    description="UEBA platform API for insider threat detection and investigation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Request ID and timing middleware
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    logger.info(
        f"{request.method} {request.url.path} - {response.status_code} - {process_time:.4f}s",
        extra={"request_id": request_id, "path": request.url.path, "method": request.method},
    )

    return response


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(anomalies.router)
app.include_router(investigations.router)
app.include_router(activity.router)
app.include_router(policies.router)
app.include_router(notifications.router)
app.include_router(ingestion.router)
app.include_router(ml.router)
app.include_router(telemetry.router)
app.include_router(banking.router)
# Detection console + employee-facing detection surfaces (spec §5, §10, §14–§19)
app.include_router(resources.router)
app.include_router(simulation.router)
app.include_router(alerts.router)
app.include_router(admin.router)


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Liveness. Answers "is this process up and can it reach its database?"

    Deliberately does *not* report the detection model. Whether a model is
    trained is a readiness question, and conflating the two means a fresh
    install reports itself unhealthy when it is merely untrained — see
    `/ready` for the distinction.

    Takes the session through `get_db` rather than opening one from
    `SessionLocal` so this endpoint is subject to the same dependency overrides
    as every other route (notably the test suite's).
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
    }


@app.get("/ready", tags=["Health"])
def readiness_check(db: Session = Depends(get_db)):
    """Readiness. Reports which detection capabilities are actually available.

    Detection degrades along a known path rather than failing: without
    telemetry there are no baselines, and without baselines there is nothing to
    train on. Those states are reportable, not fatal — the rule engine works
    regardless, so the alert queue still fills. This endpoint exists so an
    operator can tell "quiet" apart from "blind".

    Reports `ml.anomaly` — the Isolation Forest that scores risk through
    `services.detection`. The `ml.inference` stub is not consulted: it plays no
    part in any alert, so its training state says nothing about readiness.
    """
    from ml.anomaly import get_detector

    checks: dict[str, object] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ready"
        checks["telemetryEvents"] = db.query(func.count(Activity.id)).scalar() or 0
        checks["baselines"] = db.query(func.count(EmployeeBaseline.id)).scalar() or 0
    except Exception:
        checks["database"] = "unavailable"
        checks["telemetryEvents"] = 0
        checks["baselines"] = 0

    detector = get_detector()
    checks["anomalyModel"] = "ready" if detector is not None else "untrained"
    checks["modelTrainingRows"] = detector.training_rows if detector else 0

    # Only a missing database is disqualifying. An untrained model lowers
    # precision, not availability — the rules still fire.
    ready = checks["database"] == "ready"
    return {"status": "ready" if ready else "not_ready", **checks}


# Root
@app.get("/", tags=["Root"])
def root():
    return {
        "name": "Sentinel",
        "version": "1.0.0",
        "description": "Insider Threat Detection API",
        "docs": "/docs",
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred",
            }
        },
    )
