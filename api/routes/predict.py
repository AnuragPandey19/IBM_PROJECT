"""POST /api/predict — score a single transaction (company-scoped)."""
from __future__ import annotations

import logging
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company
from api.schemas.predict import PredictionResponse, ShapContribution, TransactionInput
from api.services.feature_service import get_feature_service
from api.services.model_service import get_model_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["predict"])

# Chosen so that only payloads which clearly carry pre-engineered feature
# vectors (e.g. sample rows from test_features.parquet) bypass the live
# feature pipeline. IEEE-CIS has ~390 engineered features; a legitimate
# incoming payment from a merchant portal will have <30 raw fields, well
# under this threshold, and therefore goes through `fs.build()`. 100 is a
# safe midpoint that never misclassifies either kind of payload.
_ENGINEERED_OVERLAP_THRESHOLD = 100

_PARQUET_DTYPES: dict[str, Any] = {}
_SAMPLE_POOL: dict[str, list[dict[str, Any]]] = {"fraud": [], "legit": []}


def _clean_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        if hasattr(v, "item"):
            v = v.item()
        out[k] = v
    return out


def _load_sample_pool() -> None:
    if _SAMPLE_POOL["fraud"] and _SAMPLE_POOL["legit"] and _PARQUET_DTYPES:
        return

    import pandas as pd

    root = Path(__file__).resolve().parents[2]
    candidates = [
        root / "data" / "processed" / "ieee_cis" / "samples.parquet",
        root / "data" / "processed" / "ieee_cis" / "test_features.parquet",
    ]
    parquet_path = next((p for p in candidates if p.exists()), None)
    if parquet_path is None:
        raise FileNotFoundError(
            f"Sample source not found. Tried: {[str(p) for p in candidates]}"
        )

    log.info("Loading sample pool from %s ...", parquet_path)
    df = pd.read_parquet(parquet_path)

    if "isFraud" not in df.columns:
        raise ValueError("Sample parquet missing isFraud column")

    _PARQUET_DTYPES.clear()
    for col in df.columns:
        _PARQUET_DTYPES[col] = df[col].dtype
    log.info("Cached dtypes for %d columns from parquet", len(_PARQUET_DTYPES))

    fraud_mask = df["isFraud"] == 1
    n_fraud = int(fraud_mask.sum())
    fraud_df = df[fraud_mask].sample(n=min(100, n_fraud), random_state=42)
    legit_df = df[df["isFraud"] == 0].sample(n=100, random_state=42)

    _SAMPLE_POOL["fraud"] = [_clean_row(r) for r in fraud_df.to_dict(orient="records")]
    _SAMPLE_POOL["legit"] = [_clean_row(r) for r in legit_df.to_dict(orient="records")]
    log.info(
        "Sample pool loaded: %d fraud + %d legit",
        len(_SAMPLE_POOL["fraud"]),
        len(_SAMPLE_POOL["legit"]),
    )


@router.get("/predict/samples")
def get_samples(current_user: User = Depends(require_company)):
    """Return one random fraud sample and one legit sample.

    Samples are shared demo data available to any authenticated user; the
    scoring itself will still be company-scoped when saved.
    """
    try:
        _load_sample_pool()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        log.exception("Sample pool load failed")
        raise HTTPException(500, f"Sample load failed: {e}")

    risky = random.choice(_SAMPLE_POOL["fraud"]) if _SAMPLE_POOL["fraud"] else None
    legit = random.choice(_SAMPLE_POOL["legit"]) if _SAMPLE_POOL["legit"] else None

    return {
        "risky": risky,
        "legit": legit,
        "pool_sizes": {
            "fraud": len(_SAMPLE_POOL["fraud"]),
            "legit": len(_SAMPLE_POOL["legit"]),
        },
    }


def _build_direct_features(raw_dict: dict, feature_columns: list[str]):
    import pandas as pd
    import numpy as np

    if not _PARQUET_DTYPES:
        _load_sample_pool()

    row = {}
    for col in feature_columns:
        v = raw_dict.get(col)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            v = np.nan
        row[col] = v

    df = pd.DataFrame([row], columns=feature_columns)

    for col in feature_columns:
        dt = _PARQUET_DTYPES.get(col)
        if dt is None:
            continue
        try:
            df[col] = df[col].astype(dt)
        except (ValueError, TypeError) as e:
            log.debug("Could not cast %s to %s: %s", col, dt, e)

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype("category")

    return df


@router.post("/predict", response_model=PredictionResponse)
def predict(
    payload: TransactionInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Score a single transaction end-to-end. The new Transaction and
    Prediction rows are tagged with the caller's company_id so that
    multi-tenant queries can filter them correctly.
    """
    ms = get_model_service()
    fs = get_feature_service()

    if not ms.loaded:
        try:
            ms.load()
        except FileNotFoundError as e:
            # Distinguish model missing vs pipeline missing so ops can act
            # on a clear signal instead of a generic 500.
            raise HTTPException(500, f"Stage 1 model artifact missing: {e}")

    raw_dict = payload.as_raw_dict()

    # SECURITY: Do NOT trust a client-supplied `isFraud` label — that would
    # let anyone poison their own tenant's KPIs. Ground-truth labels are
    # set only by:
    #   1. seed_transactions.py (which reads verified IEEE-CIS labels)
    #   2. A future POST /feedback endpoint (analyst review verdict)
    # Anything the client tried to sneak in via `extras.isFraud` is discarded.
    raw_dict.pop("isFraud", None)
    raw_dict.pop("is_fraud", None)
    is_fraud_val = None

    txn = Transaction(
        external_id=payload.external_id,
        transaction_dt=payload.TransactionDT,
        amount=payload.TransactionAmt,
        card1=str(payload.card1) if payload.card1 is not None else None,
        card4=payload.card4,
        card6=payload.card6,
        product_cd=payload.ProductCD,
        addr1=str(int(payload.addr1)) if payload.addr1 is not None else None,
        p_emaildomain=payload.P_emaildomain,
        device_type=payload.DeviceType,
        device_info=payload.DeviceInfo,
        raw_features=raw_dict,
        is_fraud=is_fraud_val,
        company_id=current_user.company_id,  # Multi-tenancy tag
    )
    db.add(txn)
    db.flush()

    overlap = sum(1 for c in ms.feature_columns if c in raw_dict)
    pre_engineered = overlap >= _ENGINEERED_OVERLAP_THRESHOLD

    try:
        if pre_engineered:
            log.info("Bypassing pipeline: %d/%d engineered columns in raw_dict",
                     overlap, len(ms.feature_columns))
            X = _build_direct_features(raw_dict, ms.feature_columns)
        else:
            X = fs.build(raw_dict)
    except FileNotFoundError as e:
        # Missing feature_pipeline.pkl is a very different failure mode
        # from the model file being missing — surface it clearly.
        log.exception("Feature pipeline artifact missing")
        raise HTTPException(500, f"Feature pipeline artifact missing: {e}")
    except Exception as e:
        log.exception("Feature build failed")
        raise HTTPException(500, f"Feature build failed: {e}")

    result = ms.score(X)
    raw_score = float(result["raw_scores"][0])
    calibrated = float(result["calibrated_scores"][0])
    decision = result["decisions"][0]
    latency_ms = float(result["latency_ms"])

    shap_top = ms.shap(X, top_k=5)[0]

    pred = Prediction(
        transaction_id=txn.id,
        raw_score=raw_score,
        calibrated_score=calibrated,
        decision=decision,
        model_version=ms.model_version,
        shap_top=shap_top,
        latency_ms=latency_ms,
        company_id=current_user.company_id,  # Denormalized for faster company-scoped queries
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
        model_version=ms.model_version,
        latency_ms=latency_ms,
        created_at=pred.created_at or datetime.now(timezone.utc),
    )
