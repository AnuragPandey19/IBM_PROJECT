"""GET /api/analytics/timeseries — aggregate transactions/predictions over time."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class TimeBucket(BaseModel):
    label: str            # "2026-01" for monthly, "2026" for yearly
    date: str             # ISO date of bucket start
    transactions: int
    predictions: int
    fraud_count: int
    approve_count: int
    review_count: int
    block_count: int
    avg_score: float
    volume: float         # total amount


class TimeSeries(BaseModel):
    period: str
    buckets: list[TimeBucket]
    totals: TimeBucket


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _year_key(dt: datetime) -> str:
    return f"{dt.year:04d}"


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _year_start(dt: datetime) -> datetime:
    return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/timeseries", response_model=TimeSeries)
def get_timeseries(
    period: Literal["monthly", "yearly"] = Query("monthly"),
    limit: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Return aggregated buckets of transactions + predictions over time.

    - period="monthly", limit=12 -> last 12 months
    - period="yearly", limit=5   -> last 5 years

    Aggregates are computed in Python from raw rows rather than SQL date_trunc
    to keep the code portable across SQLite (dev) and PostgreSQL (prod).
    """
    company_id = current_user.company_id
    # tz-naive UTC to stay compatible with SQLite's tz-naive Transaction/
    # Prediction.created_at columns. Postgres tolerates both.
    now = datetime.utcnow()

    # Prepare bucket keys covering the requested window
    bucket_keys: list[tuple[str, datetime]] = []
    if period == "monthly":
        # Walk back `limit` months, month by month
        y, m = now.year, now.month
        for _ in range(limit):
            key = f"{y:04d}-{m:02d}"
            bucket_start = datetime(y, m, 1)
            bucket_keys.append((key, bucket_start))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        # Reverse so oldest first
        bucket_keys.reverse()
        window_start = bucket_keys[0][1]
    else:  # yearly
        y = now.year
        for _ in range(limit):
            key = f"{y:04d}"
            bucket_start = datetime(y, 1, 1)
            bucket_keys.append((key, bucket_start))
            y -= 1
        bucket_keys.reverse()
        window_start = bucket_keys[0][1]

    # Initialize buckets with zero counts
    buckets_by_key: dict[str, dict] = {
        key: {
            "date": start.isoformat(),
            "transactions": 0,
            "predictions": 0,
            "fraud_count": 0,
            "approve_count": 0,
            "review_count": 0,
            "block_count": 0,
            "score_sum": 0.0,
            "score_n": 0,
            "volume": 0.0,
        }
        for key, start in bucket_keys
    }

    key_fn = _month_key if period == "monthly" else _year_key

    # Aggregate Transactions
    txn_rows = db.execute(
        select(Transaction.amount, Transaction.is_fraud, Transaction.created_at)
        .where(Transaction.company_id == company_id)
        .where(Transaction.created_at >= window_start)
    ).all()

    for amt, is_fraud, ts in txn_rows:
        k = key_fn(ts)
        if k not in buckets_by_key:
            continue
        b = buckets_by_key[k]
        b["transactions"] += 1
        b["volume"] += float(amt or 0)
        if is_fraud is True:
            b["fraud_count"] += 1

    # Aggregate Predictions
    pred_rows = db.execute(
        select(
            Prediction.decision,
            Prediction.calibrated_score,
            Prediction.raw_score,
            Prediction.created_at,
        )
        .where(Prediction.company_id == company_id)
        .where(Prediction.created_at >= window_start)
    ).all()

    for decision, cal, raw, ts in pred_rows:
        k = key_fn(ts)
        if k not in buckets_by_key:
            continue
        b = buckets_by_key[k]
        b["predictions"] += 1
        if decision == "approve":
            b["approve_count"] += 1
        elif decision == "review":
            b["review_count"] += 1
        elif decision == "block":
            b["block_count"] += 1
        score = cal if cal is not None else raw
        if score is not None:
            b["score_sum"] += float(score)
            b["score_n"] += 1

    # Build response
    buckets: list[TimeBucket] = []
    total_txns = total_preds = total_fraud = total_ap = total_rv = total_bl = 0
    total_score_sum = 0.0
    total_score_n = 0
    total_volume = 0.0

    for key, _ in bucket_keys:
        b = buckets_by_key[key]
        avg = (b["score_sum"] / b["score_n"]) if b["score_n"] else 0.0
        buckets.append(TimeBucket(
            label=key,
            date=b["date"],
            transactions=b["transactions"],
            predictions=b["predictions"],
            fraud_count=b["fraud_count"],
            approve_count=b["approve_count"],
            review_count=b["review_count"],
            block_count=b["block_count"],
            avg_score=round(avg, 4),
            volume=round(b["volume"], 2),
        ))
        total_txns += b["transactions"]
        total_preds += b["predictions"]
        total_fraud += b["fraud_count"]
        total_ap += b["approve_count"]
        total_rv += b["review_count"]
        total_bl += b["block_count"]
        total_score_sum += b["score_sum"]
        total_score_n += b["score_n"]
        total_volume += b["volume"]

    totals_avg = (total_score_sum / total_score_n) if total_score_n else 0.0
    totals = TimeBucket(
        label="TOTAL",
        date=bucket_keys[0][1].isoformat() if bucket_keys else now.isoformat(),
        transactions=total_txns,
        predictions=total_preds,
        fraud_count=total_fraud,
        approve_count=total_ap,
        review_count=total_rv,
        block_count=total_bl,
        avg_score=round(totals_avg, 4),
        volume=round(total_volume, 2),
    )

    return TimeSeries(period=period, buckets=buckets, totals=totals)
