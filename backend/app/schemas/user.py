from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    name: str
    email: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    status: str = "ACTIVE"


class UserCreate(UserBase):
    password: str
    role_ids: List[str] = []


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[str] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: str
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = []

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
