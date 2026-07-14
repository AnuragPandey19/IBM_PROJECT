"""Shared schema helpers.

Fixes the "backend emits naive datetime string → browser interprets as
local time" bug: `iso_utc_z` renders every datetime with an explicit 'Z'
UTC suffix that the browser's `new Date(...)` treats correctly.

Also holds `serialize_user` which used to be duplicated across auth.py
and profile.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle
    from api.db.models import User
    from api.schemas.auth import UserResponse


def iso_utc_z(dt: datetime | None) -> str | None:
    """Serialize a datetime as ISO-8601 with an explicit UTC 'Z' suffix.

    Handles both tz-aware (Postgres) and tz-naive (SQLite) values.
    Naive values are assumed to be UTC, matching our storage convention
    (`server_default=func.now()` is UTC).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    # Prefer the compact 'Z' suffix over '+00:00' for smaller payloads and
    # to match what browsers universally interpret.
    return dt.isoformat().replace("+00:00", "Z")


def serialize_user(user: "User") -> "UserResponse":
    """Build UserResponse including embedded company info.

    Previously duplicated in `api/routes/auth.py` and `api/routes/profile.py`.
    """
    # Local imports avoid the runtime cycle between schemas and routes.
    from api.schemas.auth import CompanyInfo, UserResponse

    company_info = None
    if user.company is not None:
        company_info = CompanyInfo.model_validate(user.company)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        company=company_info,
    )
