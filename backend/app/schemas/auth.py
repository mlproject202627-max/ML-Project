from pydantic import BaseModel, EmailStr
from typing import Optional


class LoginRequest(BaseModel):
    email: str
    password: str


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
    user: UserInfo
