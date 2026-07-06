"""Public /api/checkout — payment gateway simulator that runs live fraud detection.

This is the endpoint a real e-commerce merchant would call from their "Pay Now"
button. Public (no JWT required) because a checkout page is public. The demo
company's transactions get stamped with company_id = SecureBuy Demo so an
analyst can still log in on the dashboard side and see them come in live.

Design notes
------------
- Enrichment happens SERVER SIDE using hardcoded customer profiles keyed off
  card_number. This matches how a real payment gateway works: the merchant
  sends unenriched checkout data, the gateway attaches historical velocity /
  geo / customer risk features from its own store before scoring.
- Since Sparkov is a US-only synthetic training set, the profile home cities
  and merchant target_encs are chosen from the training vocabulary so the
  model actually has learned signal to reason about.
- The endpoint returns the SAME shape a real gateway (Stripe / Razorpay
  authorize call) would, so the mentor can see production-shaped JSON in
  the network tab.
"""
from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db.models import Company, Prediction, Transaction
from api.db.session import get_db
from api.schemas.checkout import (
    CheckoutRequest,
    CheckoutResponse,
    CustomerProfileInfo,
    ProfilesResponse,
)
from api.services.model_service import get_model_service
from api.services.sparkov_lookups import (
    CATEGORY_STR_TO_INT,
    GENDER_STR_TO_INT,
    STATE_STR_TO_INT,
    get_sparkov_lookups,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checkout", tags=["checkout"])

DEMO_COMPANY_NAME = "SecureBuy Electronics"
DEMO_MERCHANT_NAME = "TechMart Electronics"

DEMO_PRODUCTS = [
    {"id": "prod_001", "name": "Wireless Earbuds", "price": 79.99, "image": "🎧"},
    {"id": "prod_002", "name": "Smart Watch", "price": 249.00, "image": "⌚"},
    {"id": "prod_003", "name": "4K Smart TV", "price": 599.00, "image": "📺"},
    {"id": "prod_004", "name": "Gaming Laptop", "price": 1899.00, "image": "💻"},
    {"id": "prod_005", "name": "Premium Camera Kit", "price": 2499.00, "image": "📷"},
]


# ---------------------------------------------------------------------------
# Customer profiles — the "database" of known cards the gateway has history on
# ---------------------------------------------------------------------------
# All chosen so their home city / zip / state exist in Sparkov training data
# and their velocity averages are realistic. These are what would live in a
# real card issuer's PAN vault + spend history store.

CUSTOMER_PROFILES: dict[str, dict] = {
    "established": {
        "label": "Established Regular",
        "description": "Long-standing customer with consistent low-value spending pattern",
        "card_last4": "1234",
        "card_number_full": "4532111122221234",
        "cardholder_name": "John Smith",
        "email": "john.smith@example.com",
        "home_city": "Springfield",
        "state": "IL",
        "zip_code": 62701,
        "city_pop": 116250,
        "lat": 39.7817,
        "long": -89.6501,
        "cust_age": 35,
        "gender": "M",
        "job": "Software Developer",
        "avg_past_amt": 55.00,
        "prior_transaction_count": 200,
        "seconds_since_prev": 86400.0,   # last purchase 1 day ago
    },
    "new": {
        "label": "New Customer",
        "description": "Card issued last week — zero purchase history",
        "card_last4": "5678",
        "card_number_full": "4532111122225678",
        "cardholder_name": "Sarah Johnson",
        "email": "sarah.j@example.com",
        "home_city": "Austin",
        "state": "TX",
        "zip_code": 78701,
        "city_pop": 964254,
        "lat": 30.2672,
        "long": -97.7431,
        "cust_age": 26,
        "gender": "F",
        "job": "Marketing Manager",
        "avg_past_amt": 0.0,
        "prior_transaction_count": 0,
        "seconds_since_prev": float("nan"),
    },
    "high_spender": {
        "label": "High-Value Regular",
        "description": "Premium cardholder with high but consistent monthly spending",
        "card_last4": "9012",
        "card_number_full": "4532111122229012",
        "cardholder_name": "Michael Chen",
        "email": "mchen@example.com",
        "home_city": "San Francisco",
        "state": "CA",
        "zip_code": 94103,
        "city_pop": 873965,
        "lat": 37.7749,
        "long": -122.4194,
        "cust_age": 48,
        "gender": "M",
        "job": "Executive",
        "avg_past_amt": 500.00,
        "prior_transaction_count": 300,
        "seconds_since_prev": 43200.0,
    },
    "senior": {
        "label": "Senior Cardholder",
        "description": "Older customer with mostly grocery/gas spending",
        "card_last4": "3456",
        "card_number_full": "4532111122223456",
        "cardholder_name": "Margaret Williams",
        "email": "margaret.w@example.com",
        "home_city": "Portland",
        "state": "OR",
        "zip_code": 97201,
        "city_pop": 652503,
        "lat": 45.5152,
        "long": -122.6784,
        "cust_age": 67,
        "gender": "F",
        "job": "Retired",
        "avg_past_amt": 42.00,
        "prior_transaction_count": 150,
        "seconds_since_prev": 172800.0,
    },
}


def _resolve_profile(req: CheckoutRequest) -> tuple[str, dict]:
    """Return (profile_key, profile). If demo_profile is set, use it. Otherwise
    match by last 4 of card. Otherwise fall back to 'established'."""
    if req.demo_profile and req.demo_profile in CUSTOMER_PROFILES:
        return req.demo_profile, CUSTOMER_PROFILES[req.demo_profile]

    last4 = "".join(c for c in req.card_number if c.isdigit())[-4:]
    for key, prof in CUSTOMER_PROFILES.items():
        if prof["card_last4"] == last4:
            return key, prof

    # Unknown card → treated as new
    return "new", CUSTOMER_PROFILES["new"]


def _get_demo_company_id(db: Session) -> int:
    """Ensure a demo company exists to hold checkout transactions."""
    company = db.query(Company).filter(Company.name == DEMO_COMPANY_NAME).first()
    if company is None:
        company = Company(
            name=DEMO_COMPANY_NAME,
            industry="E-commerce",
            size="Startup (1-50)",
            use_case="Live checkout demo for CHIMERA-FD.",
            is_active=True,
        )
        db.add(company)
        db.flush()
        log.info("Created demo company: %s (id=%d)", DEMO_COMPANY_NAME, company.id)
    return company.id


# Slug → seeded Company.name mapping. Slugs are what merchant portals send
# in their /api/checkout payload so the gateway knows which merchant to
# attribute the transaction to.
COMPANY_SLUG_TO_NAME: dict[str, str] = {
    "zomato": "Zomato",
    "swiggy": "Swiggy",
    "bigbasket": "BigBasket",
    "hdfc": "HDFC Bank",
    "icici": "ICICI Bank",
    "razorpay": "Razorpay",
}


def _resolve_company_id(db: Session, company_slug: Optional[str]) -> int:
    """If a company_slug is provided by the merchant portal, look up the
    seeded company. Fall back to auto-creating SecureBuy if no slug (this
    preserves the behavior of the standalone /checkout demo page).
    """
    if company_slug:
        slug = company_slug.lower().strip()
        target_name = COMPANY_SLUG_TO_NAME.get(slug)
        if target_name:
            company = db.query(Company).filter(Company.name == target_name).first()
            if company is not None:
                return company.id
            log.warning("company_slug=%s resolved to name=%s but no seeded company found", slug, target_name)
        else:
            log.warning("unknown company_slug=%s, falling back to demo company", slug)
    return _get_demo_company_id(db)


def _generate_txn_id() -> str:
    """TXN-<7 alnum> — mimics real payment gateway ids."""
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
    return f"TXN-{suffix}"


def _generate_auth_code() -> str:
    return "AUTH-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def _build_sparkov_row(req: CheckoutRequest, profile: dict, hour: int, day_of_week: int) -> pd.DataFrame:
    """Assemble the exact 30-column DataFrame the Sparkov Stage 1 model expects,
    using the profile's velocity + geo + demographic features."""
    lk = get_sparkov_lookups()
    if not lk.loaded:
        lk.load()

    amt = float(req.amount)
    log1p_amt = float(np.log1p(amt))
    amt_cents = int(round(amt * 100)) % 100
    is_round_amt = int(amt_cents == 0)
    if amt <= 25:
        amt_bucket = 0
    elif amt <= 100:
        amt_bucket = 1
    elif amt <= 500:
        amt_bucket = 2
    else:
        amt_bucket = 3

    prior_mean = float(profile["avg_past_amt"])
    prior_count = int(profile["prior_transaction_count"])
    amt_ratio = amt / prior_mean if prior_mean > 0 and prior_count > 0 else 1.0

    seconds_since_prev = profile.get("seconds_since_prev", float("nan"))

    row = {
        "gender": GENDER_STR_TO_INT.get(profile["gender"], 0),
        "state": STATE_STR_TO_INT.get(profile["state"], 0),
        "category": CATEGORY_STR_TO_INT.get(req.merchant_category, 0),
        "amt": amt,
        "log1p_amt": log1p_amt,
        "amt_cents": amt_cents,
        "is_round_amt": is_round_amt,
        "amt_bucket": amt_bucket,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_weekend": int(day_of_week >= 5),
        "is_night": int(hour < 6),
        "unix_time": int(datetime.now().timestamp()),
        "cust_age": int(profile["cust_age"]),
        "cc_num": int(profile["card_number_full"][:12]),  # first 12 digits
        "city_pop": int(profile["city_pop"]),
        "lat": float(profile["lat"]),
        "long": float(profile["long"]),
        "merch_lat": float(profile["lat"]) + 0.5,   # merchant nearby-ish
        "merch_long": float(profile["long"]) + 0.5,
        "cust_merch_dist_km": 50.0,
        "cc_num_txn_count_before": prior_count,
        "cc_num_amt_sum_before": prior_mean * prior_count,
        "cc_num_amt_mean_before": prior_mean,
        "cc_num_seconds_since_prev": float(seconds_since_prev),
        "cc_num_amt_ratio_to_mean": float(amt_ratio),
        "merchant_target_enc": lk.merchant_enc(req.merchant_name),
        "city_target_enc": lk.city_enc(profile["home_city"]),
        "job_target_enc": lk.job_enc(profile["job"]),
        "zip_target_enc": lk.zip_enc(profile["zip_code"]),
    }
    return pd.DataFrame([row])


@router.get("/profiles", response_model=ProfilesResponse)
def get_profiles():
    """Public — returns the demo cart products + selectable customer profiles."""
    profiles = [
        CustomerProfileInfo(
            key=key,
            label=p["label"],
            description=p["description"],
            card_last4=p["card_last4"],
            home_city=p["home_city"],
            avg_past_amt=p["avg_past_amt"],
            prior_transaction_count=p["prior_transaction_count"],
        )
        for key, p in CUSTOMER_PROFILES.items()
    ]
    return ProfilesResponse(
        profiles=profiles,
        demo_merchant=DEMO_MERCHANT_NAME,
        demo_products=DEMO_PRODUCTS,
    )


@router.post("", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
):
    """Public payment authorization endpoint.

    Mimics the interface of a real payment gateway's /authorize call. The
    merchant's checkout page POSTs the raw payment details here; we enrich
    with the card's historical profile, score with Sparkov Stage 1, and
    return an approve/decline decision.
    """
    ms = get_model_service()
    if not ms.loaded:
        try:
            ms.load()
        except FileNotFoundError:
            raise HTTPException(500, "Model artifacts not available.")
    if ms.sparkov_model is None:
        raise HTTPException(503, "Fraud detection engine unavailable.")

    # Resolve customer profile (server-side enrichment)
    profile_key, profile = _resolve_profile(payload)

    # Time context — demo can force a specific hour to trigger fraud patterns
    now = datetime.now(timezone.utc)
    hour = payload.demo_hour_override if payload.demo_hour_override is not None else now.hour
    day_of_week = now.weekday()

    # Build features + score
    try:
        X = _build_sparkov_row(payload, profile, hour, day_of_week)
    except Exception as e:
        log.exception("Feature build failed for checkout")
        raise HTTPException(500, f"Fraud engine feature build failed: {e}")

    result = ms.score_sparkov(X)
    shap_top = ms.shap_sparkov(X, top_k=5)[0]

    risk_score = float(result["calibrated_scores"][0])
    decision = result["decisions"][0]      # 'approve' | 'review' | 'block'
    latency_ms = float(result["latency_ms"])

    # Route to the merchant's own company (if slug provided) or the SecureBuy
    # standalone demo company by default.
    company_id = _resolve_company_id(db, payload.company_slug)
    external_id = _generate_txn_id()
    auth_code = _generate_auth_code() if decision == "approve" else None

    txn = Transaction(
        external_id=external_id,
        transaction_dt=None,
        amount=payload.amount,
        card1=profile["card_last4"],
        card4=None,
        card6="credit",
        product_cd=f"sparkov:{payload.merchant_category}",
        addr1=profile["state"],
        p_emaildomain=(payload.cust_email.split("@")[1] if payload.cust_email and "@" in payload.cust_email else None),
        device_type="web",
        device_info=payload.merchant_name,
        raw_features={
            "__dataset__": "sparkov_checkout",
            "profile_key": profile_key,
            "merchant": payload.merchant_name,
            "cardholder": payload.cardholder_name,
            "email": payload.cust_email,
            "amount": payload.amount,
            "category": payload.merchant_category,
            "hour": hour,
            "demo_hour_override": payload.demo_hour_override,
        },
        is_fraud=None,   # unknown at checkout time — real fraud outcome only known days later
        company_id=company_id,
    )
    db.add(txn)
    db.flush()

    pred = Prediction(
        transaction_id=txn.id,
        raw_score=float(result["raw_scores"][0]),
        calibrated_score=risk_score,
        decision=decision,
        model_version=ms.sparkov_model_version,
        shap_top=shap_top,
        latency_ms=latency_ms,
        company_id=company_id,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    # Translate model decision → merchant-facing payment status
    if decision == "approve":
        status = "approved"
        reason = "Payment authorized"
    elif decision == "block":
        status = "declined"
        reason = "For your security, this transaction has been declined. Please contact your bank if this was you."
    else:
        # 'review' — soft decline for demo; a real system would step-up (3DS challenge)
        status = "review"
        reason = "Additional verification required. Please complete the security check."

    return CheckoutResponse(
        status=status,
        transaction_id=external_id,
        authorization_code=auth_code,
        amount_charged=payload.amount,
        merchant_name=payload.merchant_name,
        card_last4=profile["card_last4"],
        decision_reason=reason,
        risk_score=risk_score,
        decision_time_ms=latency_ms,
        created_at=pred.created_at or now,
        internal_prediction_id=pred.id,
        internal_shap_top=shap_top,
    )
