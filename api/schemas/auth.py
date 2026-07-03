"""Auth request/response schemas with multi-tenant Company support."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyInfo(BaseModel):
    """Company details returned alongside the user profile."""
    id: int
    name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    use_case: Optional[str] = None
    logo_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Register a new user. If company_name is provided, a new company is
    created and this user becomes its admin. If no company info is provided,
    registration is rejected (multi-tenant model requires company context).
    """
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)

    # Company details — required on first admin signup for a new company
    company_name: str = Field(min_length=2, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=64)
    size: Optional[str] = Field(default=None, max_length=32)
    use_case: Optional[str] = Field(default=None, max_length=1024)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    company: Optional[CompanyInfo] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse
