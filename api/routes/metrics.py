"""GET /api/metrics/summary — KPI aggregates for the dashboard."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import get_current_user
from api.schemas.metrics import (
    AmountStats,
    DecisionCounts,
    MetricsSummary,
    RiskyTransaction,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary", response_model=MetricsSummary)
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate KPIs for the analyst dashboard.

    All counts computed via SQL aggregates (fast even with 100k+ rows).
    """
    # ----- Transactions -----
    total_txns = db.execute(select(func.count(Transaction.id))).scalar_one() or 0
    fraud_count = db.execute(
        select(func.count(Transaction.id)).where(Transaction.is_fraud.is_(True))
    ).scalar_one() or 0

    fraud_rate = (fraud_count / total_txns) if total_txns else 0.0

    amount_total = db.execute(select(func.coalesce(func.sum(Transaction.amount), 0.0))).scalar_one() or 0.0
    amount_avg = db.execute(select(func.coalesce(func.avg(Transaction.amount), 0.0))).scalar_one() or 0.0
    amount_max = db.execute(select(func.coalesce(func.max(Transaction.amount), 0.0))).scalar_one() or 0.0

    # ----- Predictions -----
    total_preds = db.execute(select(func.count(Prediction.id))).scalar_one() or 0

    decision_rows = db.execute(
        select(Prediction.decision, func.count(Prediction.id)).group_by(Prediction.decision)
    ).all()
    decision_counts = DecisionCounts()
    for decision, count in decision_rows:
        if decision == "approve":
            decision_counts.approve = count
        elif decision == "review":
            decision_counts.review = count
        elif decision == "block":
            decision_counts.block = count

    avg_score = db.execute(
        select(func.avg(func.coalesce(Prediction.calibrated_score, Prediction.raw_score)))
    ).scalar_one()

    latest_version = db.execute(
        select(Prediction.model_version).order_by(desc(Prediction.created_at)).limit(1)
    ).scalar_one_or_none()

    # ----- Top-10 risky transactions (highest calibrated score) -----
    # Latest prediction per transaction, sorted desc
    risky_q = (
        select(Prediction, Transaction)
        .join(Transaction, Transaction.id == Prediction.transaction_id)
        .order_by(desc(func.coalesce(Prediction.calibrated_score, Prediction.raw_score)))
        .limit(10)
    )
    risky_rows = db.execute(risky_q).all()

    top_risky = [
        RiskyTransaction(
            id=t.id,
            external_id=t.external_id,
            amount=t.amount,
            calibrated_score=p.calibrated_score,
            raw_score=p.raw_score,
            decision=p.decision,
            product_cd=t.product_cd,
            is_fraud=t.is_fraud,
            created_at=t.created_at,
        )
        for p, t in risky_rows
    ]

    return MetricsSummary(
        total_transactions=total_txns,
        total_predictions=total_preds,
        fraud_count=fraud_count,
        fraud_rate=fraud_rate,
        decision_counts=decision_counts,
        avg_calibrated_score=float(avg_score) if avg_score is not None else None,
        amount_stats=AmountStats(
            total=float(amount_total),
            avg=float(amount_avg),
            max=float(amount_max),
        ),
        top_risky=top_risky,
        model_version=latest_version,
    )
