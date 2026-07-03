"""Schemas for /api/profile and /api/company update endpoints."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """Update the current user's own profile. Any field left null is unchanged.

    Password change requires the caller to prove they know the current password.
    """
    full_name: Optional[str] = Field(default=None, max_length=255)
    current_password: Optional[str] = Field(default=None)
    new_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class CompanyUpdate(BaseModel):
    """Update the caller's company. Admin-only."""
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    industry: Optional[str] = Field(default=None, max_length=64)
    size: Optional[str] = Field(default=None, max_length=32)
    use_case: Optional[str] = Field(default=None, max_length=1024)
    logo_url: Optional[str] = Field(default=None, max_length=500)
