from datetime import datetime, timezone
import logging
import uuid as uuid_mod
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from app.models.user import User, Role, user_roles
from app.models.session import UserSession
from app.models.audit_log import AuditLog, AUTH_LOGIN_FAILURE
from app.schemas.auth import (
    LoginRequest, LoginResponse, UserInfo,
    HasUsersResponse, BootstrapAdminRequest, BootstrapAdminResponse,
)

logger = logging.getLogger("sentinel.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str:
    """Best-effort client IP (respects the common proxy headers)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _record_login_session(db: Session, user: User, request: Request, session_token: str) -> None:
    """Capture the login moment: who, when, from where, on what device.

    `session_token` is an opaque random identifier, never the JWT itself —
    a stolen session row must not yield a usable credential.
    """
    db.add(UserSession(
        user_id=user.id,
        session_token=session_token,
        ip_address=_get_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "unknown")[:512],
        logged_in_at=datetime.now(timezone.utc),
        active=True,
    ))


def _record_auth_activity(
    db: Session,
    *,
    user: User,
    request: Request,
    action: str,
    event_type: str,
    severity: str = "LOW",
    metadata: dict | None = None,
    run_detection: bool = True,
) -> None:
    """Write an authentication event to the security timeline.

    Wrapped so that a telemetry problem can never turn a successful login into
    a 500. Passwords and tokens are never passed in, and never may be.
    """
    try:
        from app.services.telemetry import record_event
        record_event(
            db,
            user=user,
            action=action,
            event_type=event_type,
            request=request,
            severity=severity,
            metadata=metadata or {},
            run_detection=run_detection,
        )
    except Exception as exc:
        logger.warning("Could not record %s for %s: %s", event_type, user.id, exc)
        try:
            db.rollback()
        except Exception:
            pass


def _record_unattributable_failure(db: Session, request: Request, attempted_email: str) -> None:
    """Log a failed login for an address that matches no account.

    There is no user to attach an Activity row to, so this lands in the audit
    log as a SYSTEM actor. The attempted address is recorded because detecting
    one source spraying many accounts is the whole point; the submitted
    password is not, and never will be.
    """
    try:
        db.add(AuditLog(
            actor_id=None,
            actor_code=None,
            actor_type="SYSTEM",
            action=AUTH_LOGIN_FAILURE,
            target_type="AUTHENTICATION",
            target_id=attempted_email[:64],
            description="Failed login attempt for an unrecognised account.",
            ip_address=_get_client_ip(request),
            request_id=request.headers.get("x-request-id"),
            user_agent=(request.headers.get("user-agent") or "")[:256] or None,
            details={"attemptedEmail": attempted_email[:160], "reason": "unknown_account"},
        ))
        db.commit()
    except Exception as exc:
        logger.warning("Could not record unattributable login failure: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass


@router.get("/has-users", response_model=HasUsersResponse)
def has_users(db: Session = Depends(get_db)):
    """Public: does a real user exist yet? Drives the one-time bootstrap screen."""
    count = db.query(User).count()
    return HasUsersResponse(hasUsers=count > 0, totalUsers=count)


@router.post("/bootstrap-admin", response_model=BootstrapAdminResponse, status_code=201)
def bootstrap_admin(request: BootstrapAdminRequest, db: Session = Depends(get_db)):
    """One-time endpoint: create the first ADMIN when the instance has no users.

    Refuses once any user exists — after that, accounts are created by admins only.
    """
    if db.query(User).count() > 0:
        raise HTTPException(status_code=409, detail="Users already exist; ask an admin to create your account")

    role = db.query(Role).filter(Role.name == "ADMIN").first()
    if not role:
        raise HTTPException(status_code=500, detail="Role table not seeded; restart the API")

    email = request.email.strip().lower()
    user = User(
        name=request.name.strip(),
        email=email,
        password_hash=hash_password(request.password),
        department=request.department,
        job_title=request.job_title or "Administrator",
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id), "role": "ADMIN"})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": "ADMIN"})
    return BootstrapAdminResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        user=UserInfo(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role="ADMIN",
            department=user.department,
            jobTitle=user.job_title,
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, request_ctx: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        # Record before responding so credential-stuffing against unknown
        # addresses is still visible in the security console.
        _record_unattributable_failure(db, request_ctx, request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(request.password, user.password_hash):
        # Attributed failure — this is what feeds the failed-login rule.
        _record_auth_activity(
            db,
            user=user,
            request=request_ctx,
            action="login_failure",
            event_type="LOGIN_FAILURE",
            severity="MEDIUM",
            metadata={"reason": "bad_password"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Get primary role
    primary_role = user.roles[0].name if user.roles else "VIEWER"

    access_token = create_access_token(data={"sub": str(user.id), "role": primary_role})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": primary_role})

    # Record the real-time login session (who, when, IP, device)
    session_token = uuid_mod.uuid4().hex
    _record_login_session(db, user, request_ctx, session_token)
    db.commit()

    # Security telemetry: login moment, device learning, and the detection pass
    # that can raise a new-device or unusual-location alert.
    _record_auth_activity(
        db,
        user=user,
        request=request_ctx,
        action="login_success",
        event_type="LOGIN_SUCCESS",
        severity="LOW",
        metadata={"sessionId": session_token, "role": primary_role},
    )

    return LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
        sessionId=session_token,
        user=UserInfo(
            id=str(user.id),
            name=user.name,
            email=user.email,
            role=primary_role,
            department=user.department,
            jobTitle=user.job_title,
        )
    )


@router.post("/logout")
def logout(
    request_ctx: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close the active session for this device (matched by user-agent)."""
    ua = (request_ctx.headers.get("user-agent") or "unknown")[:512]
    session = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == current_user.id,
            UserSession.active.is_(True),
            UserSession.user_agent == ua,
        )
        .order_by(UserSession.logged_in_at.desc())
        .first()
    )
    if session:
        session.logged_out_at = datetime.now(timezone.utc)
        session.active = False
        db.commit()

    # Nothing anomalous about logging out; recorded for session-duration
    # accuracy, not for detection.
    _record_auth_activity(
        db,
        user=current_user,
        request=request_ctx,
        action="logout",
        event_type="LOGOUT",
        severity="LOW",
        run_detection=False,
    )
    return {"message": "Successfully logged out"}


@router.post("/refresh")
def refresh_token(request: dict, db: Session = Depends(get_db)):
    token = request.get("refreshToken")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refresh token required"
        )
    
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )
    
    user_uuid = uuid_mod.UUID(str(payload.get("sub")))
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    
    primary_role = user.roles[0].name if user.roles else "VIEWER"
    
    new_access_token = create_access_token(data={"sub": str(user.id), "role": primary_role})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id), "role": primary_role})
    
    return {
        "accessToken": new_access_token,
        "refreshToken": new_refresh_token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)):
    primary_role = current_user.roles[0].name if current_user.roles else "VIEWER"
    return UserInfo(
        id=str(current_user.id),
        name=current_user.name,
        email=current_user.email,
        role=primary_role,
        department=current_user.department,
        jobTitle=current_user.job_title,
    )
