import math
import secrets
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.core.dependencies import require_security_analyst, require_admin
from app.models.user import User, Role, user_roles
from app.models.anomaly import Anomaly
from app.models.risk_event import RiskEvent
from app.schemas.user import (
    UserResponse, UserListResponse, RoleResponse,
    UserCreateRequest, UserUpdateRequest, UserDeleteResponse, RoleMetaResponse,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

# ---------------------------------------------------------------------------
# Roles & access rules (banking platform spec §2)
# ---------------------------------------------------------------------------

# Sentinel platform roles + banking employee roles.
VALID_ROLES = {
    "ADMIN", "SECURITY_MANAGER", "SECURITY_ANALYST", "VIEWER",
    "TELLER", "RELATIONSHIP_MANAGER", "BRANCH_MANAGER",
    "COMPLIANCE_OFFICER", "OPERATIONS_MANAGER",
}
# Roles allowed to open the staff directory (Settings tab, read-only).
STAFF_VIEW_ROLES = {"ADMIN", "SECURITY_MANAGER", "SECURITY_ANALYST", "BRANCH_MANAGER", "OPERATIONS_MANAGER", "COMPLIANCE_OFFICER"}
VALID_STATUSES = {"ACTIVE", "SUSPENDED", "DISABLED"}


def _require_staff_view(current_user: User = Depends(get_current_user)) -> User:
    """Staff directory is visible to admins, security roles and branch/ops managers."""
    user_roles = {r.name for r in current_user.roles}
    if not user_roles & STAFF_VIEW_ROLES:
        raise HTTPException(status_code=403, detail="Staff directory access required")
    return current_user


def _next_employee_code(db: Session) -> str:
    """Generate the next sequential employee code, e.g. EMP-00001."""
    last = (
        db.query(User.employee_code)
        .filter(User.employee_code.like("EMP-%"))
        .order_by(User.employee_code.desc())
        .first()
    )
    next_num = 1
    if last and last[0]:
        try:
            next_num = int(last[0].split("-")[1]) + 1
        except (IndexError, ValueError):
            next_num = 1
    return f"EMP-{next_num:05d}"


@router.get("/meta/reference", response_model=RoleMetaResponse)
def roles_meta(
    current_user: User = Depends(get_current_user),
):
    """Role/branch options for the add-employee form (any authenticated user)."""
    return RoleMetaResponse(
        roles=sorted(VALID_ROLES),
        branches=[
            {"code": "VJA-CENTRAL", "name": "Vijayawada Central"},
            {"code": "HYD-BANJARA", "name": "Hyderabad Banjara Hills"},
            {"code": "VIZAG-NAV", "name": "Visakhapatnam Naval"},
        ],
    )


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = None,
    department: Optional[str] = None,
    status_filter: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    sort_order: Optional[str] = "desc",
    current_user: User = Depends(_require_staff_view),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )
    
    if department:
        query = query.filter(User.department == department)
    
    if status_filter:
        query = query.filter(User.status == status_filter)
    
    # Count
    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    
    # Sorting
    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Pagination
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()
    
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: User = Depends(_require_staff_view),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse.model_validate(user)


# ---------------------------------------------------------------------------
# Admin: real-user account management (no demo seeds — admins create users)
# ---------------------------------------------------------------------------


@router.get("/meta/roles", response_model=List[RoleResponse])
def list_roles(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List assignable roles."""
    return db.query(Role).order_by(Role.name).all()


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    request: UserCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin adds an employee (or platform user) with an explicit role."""
    if request.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {sorted(VALID_ROLES)}")

    email = request.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    # Employee code: use the provided one or auto-generate the next EMP-NNNNN
    employee_code = (request.employee_code or "").strip().upper() or None
    if employee_code:
        if db.query(User).filter(User.employee_code == employee_code).first():
            raise HTTPException(status_code=409, detail=f"Employee code {employee_code} is already assigned")
    else:
        employee_code = _next_employee_code(db)

    role = db.query(Role).filter(Role.name == request.role).first()
    if not role:
        raise HTTPException(status_code=500, detail="Role table not seeded; restart the API")

    user = User(
        name=request.name.strip(),
        email=email,
        password_hash=hash_password(request.password),
        department=request.department,
        job_title=request.job_title,
        status="ACTIVE",
        employee_code=employee_code,
        branch_code=(request.branch_code or None),
        branch_name=(request.branch_name or None),
        mfa_enabled=bool(request.mfa_enabled),
    )
    db.add(user)
    db.flush()
    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin updates a user (profile, status, role, optional password reset)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.name is not None:
        user.name = request.name.strip()
    if request.department is not None:
        user.department = request.department
    if request.job_title is not None:
        user.job_title = request.job_title
    if request.status is not None:
        if request.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {sorted(VALID_STATUSES)}")
        if user.id == current_user.id and request.status != "ACTIVE":
            raise HTTPException(status_code=422, detail="You cannot suspend your own account")
        user.status = request.status
    if request.password is not None:
        if len(request.password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        user.password_hash = hash_password(request.password)
    if request.role is not None:
        if request.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {sorted(VALID_ROLES)}")
        if user.id == current_user.id and request.role != "ADMIN" and "ADMIN" in {r.name for r in user.roles}:
            admins = (
                db.query(User)
                .join(user_roles, user_roles.c.user_id == User.id)
                .join(Role, Role.id == user_roles.c.role_id)
                .filter(Role.name == "ADMIN", User.status == "ACTIVE")
                .count()
            )
            if admins <= 1:
                raise HTTPException(status_code=422, detail="Cannot demote the last active admin")
        role = db.query(Role).filter(Role.name == request.role).first()
        if role:
            db.query(user_roles).filter(user_roles.c.user_id == user.id).delete()
            db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", response_model=UserDeleteResponse)
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate a user (soft delete) — telemetry history is preserved."""
    if user_id == str(current_user.id):
        raise HTTPException(status_code=422, detail="You cannot deactivate your own account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "DISABLED"
    db.commit()
    return UserDeleteResponse(id=str(user.id), status=user.status)
