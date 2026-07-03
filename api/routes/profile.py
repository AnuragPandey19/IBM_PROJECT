"""PATCH /api/profile and PATCH /api/company endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.db.models import Company, User
from api.db.session import get_db
from api.dependencies.auth import get_current_user, require_admin, require_company
from api.schemas.auth import CompanyInfo, UserResponse
from api.schemas.profile import CompanyUpdate, ProfileUpdate
from api.security import hash_password, verify_password

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])


def _serialize(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        company=(CompanyInfo.model_validate(user.company) if user.company else None),
    )


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the caller's own profile.

    - full_name is updated if provided.
    - Password change requires both current_password and new_password.
    """
    changed = False

    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip() or None
        changed = True

    # Password change flow
    if payload.new_password is not None:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to change password.",
            )
        if not verify_password(payload.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )
        current_user.hashed_password = hash_password(payload.new_password)
        changed = True

    if changed:
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        log.info("User %d updated profile", current_user.id)

    return _serialize(current_user)


@router.patch("/company", response_model=CompanyInfo)
def update_company(
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update the caller's company. Admin-only."""
    if current_user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No company associated with this user.",
        )

    company = db.query(Company).filter(Company.id == current_user.company_id).first()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    # Name uniqueness check if changing
    if payload.name is not None and payload.name.strip() != company.name:
        existing = db.query(Company).filter(Company.name == payload.name.strip()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A company named '{payload.name}' is already registered.",
            )
        company.name = payload.name.strip()

    if payload.industry is not None:
        company.industry = payload.industry.strip() or None
    if payload.size is not None:
        company.size = payload.size.strip() or None
    if payload.use_case is not None:
        company.use_case = payload.use_case.strip() or None
    if payload.logo_url is not None:
        company.logo_url = payload.logo_url.strip() or None

    db.add(company)
    db.commit()
    db.refresh(company)
    log.info("Company %d updated by user %d", company.id, current_user.id)

    return CompanyInfo.model_validate(company)


@router.get("/company/members", response_model=list[UserResponse])
def list_company_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """List all users belonging to the caller's company."""
    members = (
        db.query(User)
        .filter(User.company_id == current_user.company_id)
        .order_by(User.created_at.desc())
        .all()
    )
    return [_serialize(m) for m in members]
