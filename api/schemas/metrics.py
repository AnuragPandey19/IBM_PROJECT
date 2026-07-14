"""Response schemas for /api/metrics dashboard endpoint."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer

from api.schemas.common import iso_utc_z


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

    @field_serializer("created_at")
    def _ser_created(self, dt: datetime) -> str:
        return iso_utc_z(dt) or ""


class MetricsSummary(BaseModel):
    total_transactions: int
    total_predictions: int
    fraud_count: int                      # verified fraud (Transaction.is_fraud=True)
    fraud_rate: float                     # verified_fraud / total_transactions
    # Model-flagged rate: (review + block) / total_predictions. Complements
    # the verified fraud_rate — useful when most transactions are still
    # PENDING (label only arrives via chargeback 30-60 days later).
    model_flagged_count: int = 0
    model_flagged_rate: float = 0.0
    decision_counts: DecisionCounts
    avg_calibrated_score: Optional[float] = None
    amount_stats: AmountStats
    top_risky: list[RiskyTransaction]
    model_version: Optional[str] = None
