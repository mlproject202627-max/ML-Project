from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
import uuid
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, users, dashboard, anomalies, investigations, activity, policies, notifications, ingestion
from app.api import ml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sentinel")


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

    # Load ML model
    logger.info("Loading ML model...")
    from ml.inference import ml_service
    if ml_service.load():
        logger.info(f"ML model loaded: {ml_service.model_name} v{ml_service.model_version}")
    else:
        logger.warning("ML model not found. Run 'python ml/train.py' first.")

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


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint that tests database connectivity."""
    from ml.inference import ml_service

    # Check database
    db_status = "connected"
    try:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "ml_model": "loaded" if ml_service.is_ready else "not_loaded",
    }


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
