"""Authentication endpoints: register, login, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import User
from api.db.session import get_db
from api.dependencies.auth import get_current_user
from api.schemas.auth import Token, UserCreate, UserLogin, UserResponse
from api.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Create a new user. In production, this endpoint should be admin-only or
    disabled — use /admin/create-user instead. For dev, it's open."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that email already exists.",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Exchange email + password for a JWT."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    token = create_access_token(
        subject=user.id,
        extra={"email": user.email, "role": user.role},
    )
    return Token(
        access_token=token,
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def whoami(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user (proves the JWT works)."""
    return current_user
