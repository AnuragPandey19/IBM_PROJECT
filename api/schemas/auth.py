"""Auth-related request and response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for POST /auth/register."""
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default="analyst", pattern="^(analyst|admin|reviewer)$")


class UserLogin(BaseModel):
    """Payload for POST /auth/login."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Safe public view of a user (no password)."""
    id: int
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Response for POST /auth/login."""
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse
