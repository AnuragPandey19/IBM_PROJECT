"""Response schemas for transaction listing + detail."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class PredictionSummary(BaseModel):
    id: int
    raw_score: float
    calibrated_score: Optional[float] = None
    decision: str
    model_version: str
    latency_ms: Optional[float] = None
    shap_top: Optional[list[dict]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionSummary(BaseModel):
    """Lightweight row for list views."""
    id: int
    external_id: Optional[str] = None
    transaction_dt: Optional[int] = None
    amount: float
    card1: Optional[str] = None
    product_cd: Optional[str] = None
    p_emaildomain: Optional[str] = None
    device_type: Optional[str] = None
    is_fraud: Optional[bool] = None
    created_at: datetime

    # Latest prediction (if any)
    latest_score: Optional[float] = None
    latest_decision: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TransactionDetail(BaseModel):
    """Full detail with all predictions."""
    id: int
    external_id: Optional[str] = None
    transaction_dt: Optional[int] = None
    amount: float
    card1: Optional[str] = None
    card4: Optional[str] = None
    card6: Optional[str] = None
    product_cd: Optional[str] = None
    addr1: Optional[str] = None
    p_emaildomain: Optional[str] = None
    device_type: Optional[str] = None
    device_info: Optional[str] = None
    raw_features: Optional[dict[str, Any]] = None
    is_fraud: Optional[bool] = None
    created_at: datetime

    predictions: list[PredictionSummary] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedTransactions(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TransactionSummary]
