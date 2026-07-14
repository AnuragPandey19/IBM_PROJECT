"""Transaction input + prediction output schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from api.schemas.common import iso_utc_z


class TransactionInput(BaseModel):
    """A transaction submitted for scoring.

    Only a handful of fields are required — the rest are optional and get
    filled with defaults inside the feature pipeline. This matches how a real
    payment terminal would emit data.
    """
    external_id: Optional[str] = Field(default=None, description="Merchant-side txn id")

    # Core (IEEE-CIS naming preserved for pipeline compatibility)
    TransactionDT: int = Field(description="Seconds since a reference epoch")
    TransactionAmt: float = Field(gt=0, description="Amount in USD")
    ProductCD: Optional[str] = Field(default=None, description="Product category code")

    card1: Optional[int] = Field(default=None)
    card2: Optional[float] = Field(default=None)
    card3: Optional[float] = Field(default=None)
    card4: Optional[str] = Field(default=None, description="visa/mastercard/etc")
    card5: Optional[float] = Field(default=None)
    card6: Optional[str] = Field(default=None, description="debit/credit")

    addr1: Optional[float] = Field(default=None)
    addr2: Optional[float] = Field(default=None)

    P_emaildomain: Optional[str] = Field(default=None)
    R_emaildomain: Optional[str] = Field(default=None)

    DeviceType: Optional[str] = Field(default=None, description="desktop/mobile")
    DeviceInfo: Optional[str] = Field(default=None)

    # Any extra IEEE-CIS columns caller wants to pass (V*, C*, D*, id_*)
    extras: Optional[dict[str, Any]] = Field(default=None, description="Additional raw fields to merge")

    model_config = ConfigDict(extra="ignore")

    def as_raw_dict(self) -> dict[str, Any]:
        """Flatten to a dict ready for the feature pipeline."""
        base = self.model_dump(exclude={"extras", "external_id"}, exclude_none=True)
        if self.extras:
            base.update(self.extras)
        return base


class ShapContribution(BaseModel):
    feature: str
    value: Any
    contribution: float


class PredictionResponse(BaseModel):
    """Response for /api/predict."""
    transaction_id: int
    prediction_id: int
    raw_score: float
    calibrated_score: Optional[float] = None
    decision: str = Field(description="approve | review | block")
    shap_top: list[ShapContribution] = []
    model_version: str
    latency_ms: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _ser_created(self, dt: datetime) -> str:
        return iso_utc_z(dt) or ""
