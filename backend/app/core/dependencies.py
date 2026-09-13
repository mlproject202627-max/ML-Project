from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User


def require_role(*allowed_roles):
    """Dependency factory that checks if the current user has one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_user)):
        user_roles = {role.name for role in current_user.roles}
        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return role_checker


def require_admin(current_user: User = Depends(get_current_user)):
    user_roles = {role.name for role in current_user.roles}
    if "ADMIN" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_security_manager(current_user: User = Depends(get_current_user)):
    user_roles = {role.name for role in current_user.roles}
    if not user_roles.intersection({"ADMIN", "SECURITY_MANAGER"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security manager access required",
        )
    return current_user


def require_security_analyst(current_user: User = Depends(get_current_user)):
    user_roles = {role.name for role in current_user.roles}
    if not user_roles.intersection({"ADMIN", "SECURITY_MANAGER", "SECURITY_ANALYST"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security analyst access required",
        )
    return current_user
