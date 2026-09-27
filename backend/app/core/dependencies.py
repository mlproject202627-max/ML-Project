from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User


# ---------------------------------------------------------------------------
# Role groups (spec §3)
#
# The single source of truth for "who is what". Both the employee banking
# portal and the security console import these, so a role added here is
# immediately recognised everywhere rather than in one router and not another.
# ---------------------------------------------------------------------------

#: Operate the employee banking portal. These identities are the *subjects* of
#: monitoring — the people whose behaviour Sentinel analyses.
EMPLOYEE_ROLES = frozenset({
    "TELLER",
    "RELATIONSHIP_MANAGER",
    "BRANCH_MANAGER",
    "COMPLIANCE_OFFICER",
    "OPERATIONS_MANAGER",
})

#: Operate the security console. These identities *do* the monitoring.
ADMIN_ROLES = frozenset({"ADMIN", "SECURITY_MANAGER", "SECURITY_ANALYST"})

#: Read-only security access.
VIEWER_ROLES = frozenset({"VIEWER"})

#: Everyone who may hold a session in this system.
ALL_ROLES = EMPLOYEE_ROLES | ADMIN_ROLES | VIEWER_ROLES


def role_names(user: User) -> set[str]:
    return {role.name for role in user.roles}


def require_role(*allowed_roles):
    """Dependency factory that checks if the current user has one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_user)):
        user_roles = role_names(current_user)
        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


def require_employee(current_user: User = Depends(get_current_user)):
    """Employee-portal access.

    Deliberately *excludes* security and admin roles. Spec §3: administrators
    must not be able to act as employees — otherwise an admin could generate
    telemetry in someone else's name and poison their own investigation.
    """
    if not role_names(current_user) & EMPLOYEE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee portal access required",
        )
    return current_user


def require_staff(current_user: User = Depends(get_current_user)):
    """Any employee or security role — used for read-only reference data."""
    if not role_names(current_user) & (EMPLOYEE_ROLES | ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required",
        )
    return current_user


def require_admin(current_user: User = Depends(get_current_user)):
    user_roles = role_names(current_user)
    if "ADMIN" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_security_manager(current_user: User = Depends(get_current_user)):
    user_roles = role_names(current_user)
    if not user_roles.intersection({"ADMIN", "SECURITY_MANAGER"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security manager access required",
        )
    return current_user


def require_security_analyst(current_user: User = Depends(get_current_user)):
    user_roles = role_names(current_user)
    if not user_roles.intersection(ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security analyst access required",
        )
    return current_user


def require_security_read(current_user: User = Depends(get_current_user)):
    """Read-only security-console access: analyst roles **plus** VIEWER.

    `VIEWER` is seeded and described as "Read-only security dashboard access",
    but for a long time no guard admitted it — every security route checked
    `ADMIN_ROLES`, which excludes it. The role existed, could authenticate, and
    could then reach nothing at all. A role that cannot do what it says is
    worse than no role, because it reads as a control that is not there.

    This guard is for *GET endpoints only*. Anything that changes state —
    resolving an alert, adding a note, recomputing a baseline, running a demo
    scenario — stays on `require_security_analyst`, so a read-only role cannot
    write to the audit trail or alter an investigation. Note that reading a
    case file is itself audited (`VIEW_ALERT`), so VIEWER activity is recorded
    like anyone else's.
    """
    user_roles = role_names(current_user)
    if not user_roles.intersection(ADMIN_ROLES | VIEWER_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security console access required",
        )
    return current_user
