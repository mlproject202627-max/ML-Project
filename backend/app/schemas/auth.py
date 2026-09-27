from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


class BootstrapAdminRequest(BaseModel):
    """One-time creation of the first admin (only when no users exist)."""
    name: str
    email: EmailStr
    password: str
    department: Optional[str] = None
    job_title: Optional[str] = None


class HasUsersResponse(BaseModel):
    hasUsers: bool
    totalUsers: int


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refreshToken: str


class UserInfo(BaseModel):
    id: str
    name: str
    email: str
    role: str
    department: Optional[str] = None
    jobTitle: Optional[str] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    accessToken: str
    refreshToken: str
    sessionId: Optional[str] = None
    user: UserInfo


class BootstrapAdminResponse(BaseModel):
    accessToken: str
    refreshToken: str
    user: UserInfo
