"""SQLAlchemy ORM models.

Four tables:
  - User      : analysts + admins who log in
  - Transaction: incoming payment records
  - Prediction: model outputs per transaction (score, decision, SHAP)
  - Feedback  : analyst decisions on flagged transactions (for retraining)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="analyst", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    feedback_entries: Mapped[list["Feedback"]] = relationship(back_populates="analyst")


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    transaction_dt: Mapped[Optional[int]] = mapped_column(Integer, index=True)  # seconds
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    card1: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    card4: Mapped[Optional[str]] = mapped_column(String(64))
    card6: Mapped[Optional[str]] = mapped_column(String(64))
    product_cd: Mapped[Optional[str]] = mapped_column(String(64))
    addr1: Mapped[Optional[str]] = mapped_column(String(64))
    p_emaildomain: Mapped[Optional[str]] = mapped_column(String(128))
    device_type: Mapped[Optional[str]] = mapped_column(String(64))
    device_info: Mapped[Optional[str]] = mapped_column(String(255))

    # Raw payload as JSON for full context (all 434 columns)
    raw_features: Mapped[Optional[dict]] = mapped_column(JSON)

    # Actual label if we know it (from historical data)
    is_fraud: Mapped[Optional[bool]] = mapped_column(Boolean)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="transaction",
                                                            cascade="all, delete-orphan")


class Prediction(Base, TimestampMixin):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )

    # Raw model score (uncalibrated)
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Calibrated probability (via isotonic regression)
    calibrated_score: Mapped[Optional[float]] = mapped_column(Float)

    # Decision: approve | review | block
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    # Which model version produced this
    model_version: Mapped[str] = mapped_column(String(64), default="stage1_lightgbm_v1")

    # SHAP top-N features and contributions
    shap_top: Mapped[Optional[list]] = mapped_column(JSON)

    # Latency of scoring (milliseconds) for monitoring
    latency_ms: Mapped[Optional[float]] = mapped_column(Float)

    transaction: Mapped["Transaction"] = relationship(back_populates="predictions")
    feedback: Mapped[Optional["Feedback"]] = relationship(back_populates="prediction",
                                                          uselist=False)


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

    # confirmed_fraud | false_positive | uncertain
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(String(1024))

    prediction: Mapped["Prediction"] = relationship(back_populates="feedback")
    analyst: Mapped["User"] = relationship(back_populates="feedback_entries")
