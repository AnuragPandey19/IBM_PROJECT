"""Authentication dependencies: get_current_user, require_admin."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from api.db.models import User
from api.db.session import get_db
from api.security import decode_access_token


# HTTPBearer = simple "paste your token" dialog in Swagger UI.
# auto_error=False so we handle 401 ourselves with a clean message.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract user from JWT. Raises 401 if invalid or missing."""
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or not creds.credentials:
        raise exc

    payload = decode_access_token(creds.credentials)
    if not payload:
        raise exc

    sub = payload.get("sub")
    if not sub:
        raise exc

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise exc
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for admin-only routes."""
    if current_user.role != "admin":
        r
