from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token, get_current_user
)
from app.models.user import User, Role
from app.schemas.auth import LoginRequest, LoginResponse, UserInfo

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password_hash):
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
    db.commit()
    
    # Get primary role
    primary_role = user.roles[0].name if user.roles else "VIEWER"
    
    access_token = create_access_token(data={"sub": str(user.id), "role": primary_role})
    refresh_token = create_refresh_token(data={"sub": str(user.id), "role": primary_role})
    
    return LoginResponse(
        accessToken=access_token,
        refreshToken=refresh_token,
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
def logout(current_user: User = Depends(get_current_user)):
    # In a production system, you'd blacklist the token
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
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
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
