"""Response schemas for /api/metrics dashboard endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DecisionCounts(BaseModel):
    approve: int = 0
    review: int = 0
    block: int = 0


class AmountStats(BaseModel):
    total: float = 0.0
    avg: float = 0.0
    max: float = 0.0


class RiskyTransaction(BaseModel):
    id: int
    external_id: Optional[str] = None
    amount: float
    calibrated_score: Optional[float] = None
    raw_score: float
    decision: str
    product_cd: Optional[str] = None
    is_fraud: Optional[bool] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MetricsSummary(BaseModel):
    total_transactions: int
    total_predictions: int
    fraud_count: int
    fraud_rate: float  # 0.0 - 1.0
    decision_counts: DecisionCounts
    avg_calibrated_score: Optional[float] = None
    amount_stats: AmountStats
    top_risky: list[RiskyTransaction]
    model_version: Optional[str] = None
