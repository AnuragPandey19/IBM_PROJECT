"""SQLAlchemy ORM models.

Five tables:
  - Company    : tenant organization; owns users, transactions, and predictions
  - User       : analysts + admins scoped to a company
  - Transaction: incoming payment records scoped to a company
  - Prediction : model outputs scoped to a company
  - Feedback   : analyst decisions on flagged transactions (for retraining)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    """Multi-tenant boundary. All data is company-scoped."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(64))
    size: Mapped[Optional[str]] = mapped_column(String(32))
    use_case: Mapped[Optional[str]] = mapped_column(String(1024))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="company")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="company")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True,
    )
    company: Mapped[Optional["Company"]] = relationship(back_populates="users")

    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="analyst")


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    transaction_dt: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    card1: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    card4: Mapped[Optional[str]] = mapped_column(String(64))
    card6: Mapped[Optional[str]] = mapped_column(String(64))
    product_cd: Mapped[Optional[str]] = mapped_column(String(64))
    addr1: Mapped[Optional[str]] = mapped_column(String(64))
    p_emaildomain: Mapped[Optional[str]] = mapped_column(String(128))
    device_type: Mapped[Optional[str]] = mapped_column(String(64))
    device_info: Mapped[Optional[str]] = mapped_column(String(255))

    raw_features: Mapped[Optional[dict]] = mapped_column(JSON)
    is_fraud: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Multi-tenancy: this transaction belongs to a specific company
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True,
    )
    company: Mapped[Optional["Company"]] = relationship(back_populates="transactions")

    predictions: Mapped[list["Prediction"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    calibrated_score: Mapped[Optional[float]] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(64), default="stage1_lightgbm_v1")
    shap_top: Mapped[Optional[list]] = mapped_column(JSON)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)

    # Multi-tenancy: denormalized from transaction for faster company-scoped queries
    company_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True,
    )

    transaction: Mapped["Transaction"] = relationship(back_populates="predictions")
    feedback: Mapped[Optional["Feedback"]] = relationship(
        back_populates="prediction", uselist=False
    )


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id", ondelete="CASCADE"),
        index=True, nullable=False, unique=True,
    )
    analyst_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True, nullable=False,
    )

    verdict: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1024))

    prediction: Mapped["Prediction"] = relationship(back_populates="feedback")
    analyst: Mapped["User"] = relationship(back_populates="feedback_entries")
