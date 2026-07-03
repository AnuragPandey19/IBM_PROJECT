"""Auth dependency: verifies JWT and loads current User with company relation."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from api.db.models import User
from api.db.session import get_db
from api.security import decode_access_token


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None or not creds.credentials:
        raise exc

    payload = decode_access_token(creds.credentials)
    if payload is None or "sub" not in payload:
        raise exc

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise exc

    # Eager-load company so downstream code can access user.company without extra query
    user = (
        db.query(User)
        .options(joinedload(User.company))
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active:
        raise exc
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency for admin-only routes."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_company(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the user is scoped to a company (multi-tenancy)."""
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has no company association. Contact support.",
        )
    return current_user
