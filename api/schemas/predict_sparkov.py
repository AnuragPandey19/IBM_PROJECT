"""Sparkov transaction input schema (human-interpretable fields).

Unlike IEEE-CIS which uses anonymized encoded features (card1=17188, V127=0.34),
Sparkov uses real merchant names, cities, amounts, categories. This is the
schema the frontend Live Predict (Sparkov mode) form submits.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SparkovTransactionInput(BaseModel):
    """A Sparkov-style transaction submitted for scoring.

    Only `amt`, `category`, `hour`, `merchant`, `city`, `state`, `gender`,
    `cust_age` are strictly required. Everything else is auto-derived or has
    sensible defaults so demo users don't have to fill 20 fields.
    """
    external_id: Optional[str] = Field(default=None, description="Merchant-side txn id")

    # === Required human-facing fields ===
    amt: float = Field(gt=0, description="Transaction amount in USD")
    category: str = Field(description="One of Sparkov's 14 merchant categories, e.g. 'grocery_pos'")
    hour: int = Field(ge=0, le=23, description="Hour of day 0-23")
    merchant: str = Field(description="Merchant name (e.g. 'fraud_Kirlin and Sons')")
    city: str = Field(description="Customer city")
    state: str = Field(description="US state 2-letter code (e.g. 'IL')")
    gender: str = Field(description="'F' or 'M'")
    cust_age: int = Field(ge=0, le=120, description="Cardholder age in years")

    # === Optional but recommended ===
    day_of_week: Optional[int] = Field(default=2, ge=0, le=6, description="0=Mon .. 6=Sun")
    job: Optional[str] = Field(default=None)
    zip: Optional[int] = Field(default=None)
    city_pop: Optional[int] = Field(default=None)
    cust_merch_dist_km: Optional[float] = Field(default=None, description="If omitted, derived from lat/long")

    # === Geographic (optional — filled from city lookup if omitted) ===
    lat: Optional[float] = Field(default=None)
    long: Optional[float] = Field(default=None)
    merch_lat: Optional[float] = Field(default=None)
    merch_long: Optional[float] = Field(default=None)

    # === Velocity/history (optional — treated as "new customer" if omitted) ===
    cc_num: Optional[int] = Field(default=None)
    cc_num_txn_count_before: Optional[int] = Field(default=0)
    cc_num_amt_sum_before: Optional[float] = Field(default=0.0)
    cc_num_amt_mean_before: Optional[float] = Field(default=0.0)
    cc_num_seconds_since_prev: Optional[float] = Field(default=None)

    # === Ground truth flag (for demo — lets sample-loaded rows keep their label) ===
    is_fraud: Optional[int] = Field(default=None)

    model_config = ConfigDict(extra="ignore")


class SparkovLookupResponse(BaseModel):
    """Dropdown options + hints for the frontend Sparkov form."""
    categories: list[str]
    genders: list[str]
    states: list[str]
    top_merchants: list[str]
    top_cities: list[dict]
    top_jobs: list[str]


class SparkovSampleRow(BaseModel):
    """One human-readable sample row for demo pre-fill."""
    amt: float
    category: str
    hour: int
    day_of_week: int
    merchant: str
    city: str
    state: str
    gender: str
    cust_age: int
    cust_merch_dist_km: float
    job: Optional[str] = None
    zip: Optional[int] = None
    city_pop: Optional[int] = None
    lat: Optional[float] = None
    long: Optional[float] = None
    merch_lat: Optional[float] = None
    merch_long: Optional[float] = None
    cc_num: Optional[int] = None
    cc_num_txn_count_before: Optional[int] = None
    cc_num_amt_sum_before: Optional[float] = None
    cc_num_amt_mean_before: Optional[float] = None
    cc_num_seconds_since_prev: Optional[float] = None
    is_fraud: int
    label: str  # "FRAUD" or "LEGIT"


class SparkovSamplesResponse(BaseModel):
    """Batch of fraud + legit samples the frontend can present as buttons."""
    fraud: list[SparkovSampleRow]
    legit: list[SparkovSampleRow]
    pool_sizes: dict[str, int]
