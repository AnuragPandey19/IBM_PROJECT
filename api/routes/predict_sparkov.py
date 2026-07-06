"""Sparkov-mode prediction routes.

Sparkov (Kaggle Sparkov Credit Card Fraud dataset) uses HUMAN-READABLE
transaction fields: real merchant names, cities, categories, dollar amounts.
This lets analysts / mentors reason about "does this input look fraudulent?"
which is impossible on IEEE-CIS's anonymized `card1=17188, V127=0.34` inputs.

Endpoints:
  POST /api/predict/sparkov          -- score a human-readable transaction
  GET  /api/predict/sparkov/lookups  -- dropdown values for the frontend form
  GET  /api/predict/sparkov/samples  -- pre-fill demo fraud+legit rows
"""
from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company
from api.schemas.predict import PredictionResponse, ShapContribution
from api.schemas.predict_sparkov import (
    SparkovLookupResponse,
    SparkovSampleRow,
    SparkovSamplesResponse,
    SparkovTransactionInput,
)
from api.services.model_service import get_model_service
from api.services.sparkov_lookups import (
    CATEGORY_INT_TO_STR,
    CATEGORY_LABELS,
    CATEGORY_STR_TO_INT,
    GENDER_INT_TO_STR,
    GENDER_STR_TO_INT,
    STATE_CODES,
    STATE_INT_TO_STR,
    STATE_STR_TO_INT,
    get_sparkov_lookups,
)

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/predict/sparkov", tags=["predict-sparkov"])


# ---------------------------------------------------------------------------
# Sample pool (loaded lazily from test_features.parquet, cached)
# ---------------------------------------------------------------------------
_SAMPLE_POOL: dict[str, list[dict[str, Any]]] = {"fraud": [], "legit": []}


def _to_int_or_none(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _to_float_or_none(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _row_to_sample(row: dict) -> Optional[dict]:
    """Convert a raw parquet row into a demo-friendly sample dict."""
    try:
        category_int = int(row.get("category", 0) or 0)
        gender_int = int(row.get("gender", 0) or 0)
        state_int = int(row.get("state", 0) or 0)
        is_fraud = int(row.get("is_fraud", 0) or 0)
        return {
            "amt": float(row.get("amt", 0.0)),
            "category": CATEGORY_INT_TO_STR.get(category_int, f"category_{category_int}"),
            "hour": int(row.get("hour", 0)),
            "day_of_week": int(row.get("day_of_week", 0)),
            "merchant": str(row.get("merchant", "unknown")),
            "city": str(row.get("city", "unknown")),
            "state": STATE_INT_TO_STR.get(state_int, "??"),
            "gender": GENDER_INT_TO_STR.get(gender_int, "?"),
            "cust_age": int(row.get("cust_age", 0)),
            "cust_merch_dist_km": float(row.get("cust_merch_dist_km", 0.0) or 0.0),
            "job": str(row.get("job", "")) if row.get("job") else None,
            "zip": _to_int_or_none(row.get("zip")),
            "city_pop": _to_int_or_none(row.get("city_pop")),
            "lat": _to_float_or_none(row.get("lat")),
            "long": _to_float_or_none(row.get("long")),
            "merch_lat": _to_float_or_none(row.get("merch_lat")),
            "merch_long": _to_float_or_none(row.get("merch_long")),
            "cc_num": _to_int_or_none(row.get("cc_num")),
            "cc_num_txn_count_before": _to_int_or_none(row.get("cc_num_txn_count_before")),
            "cc_num_amt_sum_before": _to_float_or_none(row.get("cc_num_amt_sum_before")),
            "cc_num_amt_mean_before": _to_float_or_none(row.get("cc_num_amt_mean_before")),
            "cc_num_seconds_since_prev": _to_float_or_none(row.get("cc_num_seconds_since_prev")),
            "is_fraud": is_fraud,
            "label": "FRAUD" if is_fraud else "LEGIT",
        }
    except (TypeError, ValueError) as e:
        log.debug("Sample row conversion failed: %s", e)
        return None


def _load_sample_pool() -> None:
    if _SAMPLE_POOL["fraud"] and _SAMPLE_POOL["legit"]:
        return

    path = settings.sparkov_features_path
    if not path.exists():
        raise FileNotFoundError(f"Sparkov features parquet not found: {path}")

    log.info("Loading Sparkov sample pool from %s", path)
    df = pd.read_parquet(path)

    fraud_rows = df[df["is_fraud"] == 1].sample(
        n=min(50, int((df["is_fraud"] == 1).sum())), random_state=42
    )
    legit_rows = df[df["is_fraud"] == 0].sample(n=50, random_state=42)

    for r in fraud_rows.to_dict(orient="records"):
        s = _row_to_sample(r)
        if s is not None:
            _SAMPLE_POOL["fraud"].append(s)
    for r in legit_rows.to_dict(orient="records"):
        s = _row_to_sample(r)
        if s is not None:
            _SAMPLE_POOL["legit"].append(s)

    log.info("Sparkov sample pool: %d fraud + %d legit",
             len(_SAMPLE_POOL["fraud"]), len(_SAMPLE_POOL["legit"]))


# ---------------------------------------------------------------------------
# Feature building: human-readable input -> 30-column model input
# ---------------------------------------------------------------------------

def _build_sparkov_features(payload: SparkovTransactionInput) -> pd.DataFrame:
    """Turn user's human-readable submission into the exact 30-column DataFrame
    the Sparkov LightGBM model expects.
    """
    lk = get_sparkov_lookups()
    if not lk.loaded:
        lk.load()

    # Encode categoricals with hard-coded LabelEncoder mappings
    category_int = CATEGORY_STR_TO_INT.get(payload.category, 0)
    gender_int = GENDER_STR_TO_INT.get(payload.gender.upper(), 0)
    state_int = STATE_STR_TO_INT.get(payload.state.upper(), 0)

    # Target-encoded lookups (fallback to global mean on unseen values)
    merchant_te = lk.merchant_enc(payload.merchant)
    city_te = lk.city_enc(payload.city)
    job_te = lk.job_enc(payload.job) if payload.job else lk.global_target_mean
    zip_te = lk.zip_enc(payload.zip) if payload.zip is not None else lk.global_target_mean

    # Amount-derived features (exactly as add_sparkov_amount)
    amt = float(payload.amt)
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

    # Temporal-derived features
    is_night = int(payload.hour < 6)
    day_of_week = int(payload.day_of_week if payload.day_of_week is not None else 2)
    is_weekend = int(day_of_week >= 5)

    # Velocity — user's inputs OR "new customer" defaults
    prior_count = int(payload.cc_num_txn_count_before or 0)
    prior_sum = float(payload.cc_num_amt_sum_before or 0.0)
    prior_mean = float(payload.cc_num_amt_mean_before or 0.0)
    seconds_since_prev = payload.cc_num_seconds_since_prev
    if seconds_since_prev is None:
        seconds_since_prev = float("nan")
    if prior_mean > 0 and prior_count > 0:
        amt_ratio = amt / prior_mean
    else:
        amt_ratio = 1.0

    # Geographic distance — user supplied or derived from lat/long
    dist_km = payload.cust_merch_dist_km
    if dist_km is None and None not in (
        payload.lat, payload.long, payload.merch_lat, payload.merch_long
    ):
        dist_km = _haversine_km(
            payload.lat, payload.long,
            payload.merch_lat, payload.merch_long,
        )
    if dist_km is None:
        dist_km = 0.0

    # City metadata (uses supplied values, else falls back to lookup)
    city_pop = payload.city_pop if payload.city_pop is not None else 0
    lat = payload.lat if payload.lat is not None else 0.0
    long_ = payload.long if payload.long is not None else 0.0
    merch_lat = payload.merch_lat if payload.merch_lat is not None else 0.0
    merch_long = payload.merch_long if payload.merch_long is not None else 0.0
    unix_time = 1600000000  # a plausible unix time (Sept 2020) — model uses this as a rank feature
    cc_num = payload.cc_num if payload.cc_num is not None else 0

    row = {
        # Categoricals (label-encoded)
        "gender": gender_int,
        "state": state_int,
        "category": category_int,
        # Amounts + amount-derived
        "amt": amt,
        "log1p_amt": log1p_amt,
        "amt_cents": amt_cents,
        "is_round_amt": is_round_amt,
        "amt_bucket": amt_bucket,
        # Temporal
        "hour": int(payload.hour),
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "is_night": is_night,
        "unix_time": unix_time,
        # Customer
        "cust_age": int(payload.cust_age),
        "cc_num": cc_num,
        "city_pop": int(city_pop),
        # Geography
        "lat": float(lat),
        "long": float(long_),
        "merch_lat": float(merch_lat),
        "merch_long": float(merch_long),
        "cust_merch_dist_km": float(dist_km),
        # Velocity
        "cc_num_txn_count_before": prior_count,
        "cc_num_amt_sum_before": prior_sum,
        "cc_num_amt_mean_before": prior_mean,
        "cc_num_seconds_since_prev": float(seconds_since_prev),
        "cc_num_amt_ratio_to_mean": float(amt_ratio),
        # Target-encoded
        "merchant_target_enc": merchant_te,
        "city_target_enc": city_te,
        "job_target_enc": job_te,
        "zip_target_enc": zip_te,
    }

    return pd.DataFrame([row])


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    lat1r, lat2r = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return float(2 * R * np.arcsin(np.sqrt(a)))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/lookups", response_model=SparkovLookupResponse)
def get_lookups(_: User = Depends(require_company)):
    """Return dropdown values for the frontend Sparkov form."""
    try:
        lk = get_sparkov_lookups()
        lk.load()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    return SparkovLookupResponse(
        categories=CATEGORY_LABELS,
        genders=["F", "M"],
        states=STATE_CODES,
        top_merchants=lk.top_merchants,
        top_cities=lk.top_cities,
        top_jobs=lk.top_jobs,
    )


@router.get("/samples", response_model=SparkovSamplesResponse)
def get_samples(_: User = Depends(require_company)):
    """Return 5 fraud + 5 legit random real transactions for demo pre-fill.

    Kept for backward compatibility with earlier UI. New "blind" demo flow
    should use /random instead (returns one row with the fraud label hidden
    from the immediate UI until the analyst explicitly reveals it).
    """
    try:
        _load_sample_pool()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))

    fraud_pick = random.sample(
        _SAMPLE_POOL["fraud"], k=min(5, len(_SAMPLE_POOL["fraud"]))
    )
    legit_pick = random.sample(
        _SAMPLE_POOL["legit"], k=min(5, len(_SAMPLE_POOL["legit"]))
    )
    return SparkovSamplesResponse(
        fraud=[SparkovSampleRow(**r) for r in fraud_pick],
        legit=[SparkovSampleRow(**r) for r in legit_pick],
        pool_sizes={"fraud": len(_SAMPLE_POOL["fraud"]), "legit": len(_SAMPLE_POOL["legit"])},
    )


@router.get("/random", response_model=SparkovSampleRow)
def get_random_sample(_: User = Depends(require_company)):
    """Return ONE random real transaction with the ground truth label
    included in the payload but not visually surfaced by the demo UI until
    the user explicitly reveals it.

    Balancing: 50/50 fraud/legit draw so the demo actually hits fraud cases
    frequently (real-world rate is ~0.24%, which would make live demo hits
    take forever). Documented in presentation as "blind but balanced demo".
    """
    try:
        _load_sample_pool()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))

    pools_ok = bool(_SAMPLE_POOL["fraud"]) and bool(_SAMPLE_POOL["legit"])
    if not pools_ok:
        raise HTTPException(503, "Sample pools not fully loaded.")

    from_fraud_pool = random.random() < 0.5
    pool = _SAMPLE_POOL["fraud"] if from_fraud_pool else _SAMPLE_POOL["legit"]
    row = random.choice(pool)
    return SparkovSampleRow(**row)


@router.post("", response_model=PredictionResponse)
def predict_sparkov(
    payload: SparkovTransactionInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Score a human-readable Sparkov-style transaction."""
    ms = get_model_service()
    if not ms.loaded:
        try:
            ms.load()
        except FileNotFoundError:
            raise HTTPException(500, "Model artifacts not loaded on this server.")

    if ms.sparkov_model is None:
        raise HTTPException(
            503, "Sparkov model not available on this deployment."
        )

    try:
        X = _build_sparkov_features(payload)
    except Exception as e:
        log.exception("Sparkov feature build failed")
        raise HTTPException(400, f"Feature build failed: {e}")

    # ---- Persist raw transaction ----
    # We stash the raw human-readable dict into raw_features with a marker so
    # the dashboard can tell IEEE-CIS and Sparkov rows apart.
    raw_dict = payload.model_dump(exclude_none=True)
    raw_dict["__dataset__"] = "sparkov"

    txn = Transaction(
        external_id=payload.external_id,
        transaction_dt=None,
        amount=payload.amt,
        card1=str(payload.cc_num) if payload.cc_num is not None else None,
        card4=None,
        card6=None,
        product_cd=f"sparkov:{payload.category}",  # Reusing product_cd column for dataset+category
        addr1=payload.state,
        p_emaildomain=None,
        device_type=None,
        device_info=payload.merchant,
        raw_features=raw_dict,
        is_fraud=(bool(payload.is_fraud) if payload.is_fraud is not None else None),
        company_id=current_user.company_id,
    )
    db.add(txn)
    db.flush()

    # ---- Score + SHAP ----
    result = ms.score_sparkov(X)
    shap_top = ms.shap_sparkov(X, top_k=5)[0]

    raw_score = float(result["raw_scores"][0])
    calibrated = float(result["calibrated_scores"][0])
    decision = result["decisions"][0]
    latency_ms = float(result["latency_ms"])

    pred = Prediction(
        transaction_id=txn.id,
        raw_score=raw_score,
        calibrated_score=calibrated,
        decision=decision,
        model_version=ms.sparkov_model_version,
        shap_top=shap_top,
        latency_ms=latency_ms,
        company_id=current_user.company_id,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)

    return PredictionResponse(
        transaction_id=txn.id,
        prediction_id=pred.id,
        raw_score=raw_score,
        calibrated_score=calibrated,
        decision=decision,
        shap_top=[ShapContribution(**s) for s in shap_top],
        model_version=ms.sparkov_model_version,
        latency_ms=latency_ms,
        created_at=pred.created_at or datetime.now(timezone.utc),
    )
