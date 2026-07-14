"""Public checkout endpoint schemas.

This is the payment-gateway-facing side of CHIMERA-FD. In a real deployment
the merchant's frontend calls this endpoint on their "Pay Now" button.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from api.schemas.common import iso_utc_z


class CheckoutRequest(BaseModel):
    """Payment payload as it would come in from a merchant's checkout form.

    All the SECRET / RISK-relevant enrichment (customer velocity, home city,
    historical amount patterns) happens server-side using the profile keyed
    off the card number — this mirrors how a real payment gateway pipelines
    unenriched checkout data through a fraud engine.
    """
    # Payment
    card_number: str = Field(min_length=8, max_length=32)
    cardholder_name: str = Field(min_length=1, max_length=64)
    card_expiry: Optional[str] = None
    card_cvv: Optional[str] = None

    # Order
    amount: float = Field(gt=0, description="Charge amount in USD")
    merchant_name: str = Field(default="TechMart Electronics")
    merchant_category: str = Field(default="shopping_net")

    # Optional customer identity
    cust_email: Optional[str] = None

    # Multi-merchant routing: which company's dashboard does this transaction
    # belong to? A real payment gateway would derive this from an API key
    # embedded in the merchant integration. In the demo, the merchant portal
    # frontend hardcodes its own slug.
    company_slug: Optional[str] = Field(default=None,
                                        description="Slug of the merchant company (zomato, swiggy, bigbasket)")

    # DEMO CONTROLS (would not exist in a real gateway, but critical here so
    # the mentor can steer test cases without needing to know the internals)
    demo_hour_override: Optional[int] = Field(default=None, ge=0, le=23,
                                              description="Force a specific hour of day for demo purposes")
    demo_profile: Optional[str] = Field(default=None,
                                        description="Force a specific customer profile: established | new | high_spender")

    model_config = ConfigDict(extra="ignore")


class CheckoutResponse(BaseModel):
    """Merchant-facing response — mirrors what Stripe/Razorpay would return."""
    status: str = Field(description="'approved' | 'declined' | 'review'")
    transaction_id: str
    authorization_code: Optional[str] = None
    amount_charged: float
    merchant_name: str
    card_last4: str
    decision_reason: str
    risk_score: float
    decision_time_ms: float
    created_at: datetime

    # Internal fields — visible on the "developer" view, hidden on the merchant checkout success screen
    internal_prediction_id: int
    internal_shap_top: list[dict] = []

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _ser_created(self, dt: datetime) -> str:
        return iso_utc_z(dt) or ""


class CustomerProfileInfo(BaseModel):
    """Used by GET /api/checkout/profiles to populate the demo profile picker."""
    key: str
    label: str
    description: str
    card_last4: str
    home_city: str
    avg_past_amt: float
    prior_transaction_count: int


class ProfilesResponse(BaseModel):
    profiles: list[CustomerProfileInfo]
    demo_merchant: str
    demo_products: list[dict]
