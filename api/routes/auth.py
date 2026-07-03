"""Authentication routes: register (creates company + admin), login, me."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import Company, User
from api.db.session import get_db
from api.dependencies.auth import get_current_user
from api.schemas.auth import CompanyInfo, Token, UserCreate, UserLogin, UserResponse
from api.security import create_access_token, hash_password, verify_password

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _serialize_user(user: User) -> UserResponse:
    """Build UserResponse including embedded company info."""
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


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new company + its first admin user.

    Every public signup creates a fresh company with the caller as its admin.
    The company_name must be unique across the platform. If an existing
    company shares the name, registration is rejected with 409.

    Existing analysts who want to join an existing company must be invited
    by their company's admin (via a future /users/invite endpoint, not yet
    implemented). This endpoint is exclusively for new-company signups.
    """
    # Check email uniqueness
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Check company name uniqueness
    existing_company = db.query(Company).filter(Company.name == payload.company_name).first()
    if existing_company is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A company named '{payload.company_name}' is already registered. "
                "Contact your company admin for an invitation."
            ),
        )

    # Create the company
    company = Company(
        name=payload.company_name,
        industry=payload.industry,
        size=payload.size,
        use_case=payload.use_case,
        is_active=True,
    )
    db.add(company)
    db.flush()  # assigns company.id

    # Create the admin user for this company
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin",  # First user of a new company is its admin
        is_active=True,
        company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log.info(
        "Registered new company '%s' (id=%d) with admin %s (id=%d)",
        company.name, company.id, user.email, user.id,
    )
    return _serialize_user(user)


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and return a JWT token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    token = create_access_token(subject=user.id, extra={"role": user.role})
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.jwt_access_token_expire_minutes,
        user=_serialize_user(user),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile with company info."""
    return _serialize_user(current_user)
