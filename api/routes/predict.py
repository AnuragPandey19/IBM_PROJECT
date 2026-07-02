"""POST /api/predict — score a single transaction."""
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
from api.dependencies.auth import get_current_user
from api.schemas.predict import PredictionResponse, ShapContribution, TransactionInput
from api.services.feature_service import get_feature_service
from api.services.model_service import get_model_service

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["predict"])

_ENGINEERED_OVERLAP_THRESHOLD = 100

# Cached dtypes from parquet — populated at first sample load
# Maps column name -> pandas dtype (may be CategoricalDtype for categorical cols)
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
    # Prefer the small pre-sampled file (~3 MB, git-friendly for HF Spaces).
    # Fall back to the full test_features.parquet when running locally.
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

    # Cache dtypes for each column — these are the exact dtypes the model expects
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
def get_samples(current_user: User = Depends(get_current_user)):
    """Return one random fraud sample and one legit sample."""
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
    """Build a scoring-ready DataFrame that matches the parquet dtype layout.

    Uses cached parquet dtypes so categorical columns are declared correctly
    for LightGBM. As a defensive fallback for the string-object case, we
    explicitly cast object columns to category dtype which LightGBM accepts.
    """
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

    # Apply cached parquet dtypes column-by-column
    for col in feature_columns:
        dt = _PARQUET_DTYPES.get(col)
        if dt is None:
            continue
        try:
            df[col] = df[col].astype(dt)
        except (ValueError, TypeError) as e:
            log.debug("Could not cast %s to %s: %s", col, dt, e)

    # Defensive: any object-dtype column must be converted to category so
    # LightGBM can accept it (LightGBM rejects raw object/string columns).
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype("category")

    return df


@router.post("/predict", response_model=PredictionResponse)
def predict(
    payload: TransactionInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a single transaction end-to-end."""
    ms = get_model_service()
    fs = get_feature_service()

    if not ms.loaded:
        try:
            ms.load()
        except FileNotFoundError:
            raise HTTPException(500, "Model artifacts not loaded on this server.")

    raw_dict = payload.as_raw_dict()

    # Extract ground-truth label if caller supplied one in extras
    # (e.g. when scoring a labelled sample from the parquet). Real-world API
    # callers won't send this — it stays None for unknown.
    is_fraud_val = raw_dict.get("isFraud")
    if is_fraud_val is not None:
        try:
            is_fraud_val = bool(int(is_fraud_val))
        except (TypeError, ValueError):
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
