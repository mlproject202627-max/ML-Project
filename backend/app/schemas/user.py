from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID


def _coerce_uuid(value):
    """Accept UUID objects from SQLAlchemy and coerce them to str."""
    if isinstance(value, UUID):
        return str(value)
    return value


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

    _coerce = field_validator("id", mode="before")(_coerce_uuid)

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: str
    employee_code: Optional[str] = None
    branch_code: Optional[str] = None
    branch_name: Optional[str] = None
    mfa_enabled: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[RoleResponse] = []

    _coerce = field_validator("id", mode="before")(_coerce_uuid)

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    items: List[UserResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class UserCreateRequest(BaseModel):
    """Admin payload for adding an employee / platform user."""
    name: str
    email: EmailStr
    password: str
    role: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    employee_code: Optional[str] = None   # e.g. EMP-10452; auto-generated when omitted
    branch_code: Optional[str] = None     # e.g. VJA-CENTRAL
    branch_name: Optional[str] = None     # e.g. Vijayawada Central
    mfa_enabled: bool = False


class UserUpdateRequest(BaseModel):
    """Admin payload for updating a user; unset fields are left alone."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    status: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None


class UserDeleteResponse(BaseModel):
    id: str
    status: str


class BranchOption(BaseModel):
    code: str
    name: str


class RoleMetaResponse(BaseModel):
    """Form options for the add-employee panel."""
    roles: List[str]
    branches: List[BranchOption]
