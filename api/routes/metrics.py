"""GET /api/metrics/summary — KPI aggregates for the dashboard (company-scoped)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import Integer, desc, func, select
from sqlalchemy.orm import Session

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company
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
    current_user: User = Depends(require_company),
):
    """Aggregate KPIs for the analyst dashboard, scoped to caller's company."""
    company_id = current_user.company_id

    # ----- Transactions (single aggregate query) -----
    txn_agg = db.execute(
        select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0.0),
            func.coalesce(func.avg(Transaction.amount), 0.0),
            func.coalesce(func.max(Transaction.amount), 0.0),
            func.coalesce(func.sum(
                # Portable "bool → int" for counting verified-fraud rows
                # without a case() when Transaction.is_fraud is nullable.
                func.cast(Transaction.is_fraud, Integer)
            ), 0),
        )
        .where(Transaction.company_id == company_id)
    ).one()
    total_txns = int(txn_agg[0] or 0)
    amount_total = float(txn_agg[1] or 0.0)
    amount_avg = float(txn_agg[2] or 0.0)
    amount_max = float(txn_agg[3] or 0.0)
    fraud_count = int(txn_agg[4] or 0)
    fraud_rate = (fraud_count / total_txns) if total_txns else 0.0

    # ----- Predictions: decision counts + score avg in one grouped query -----
    decision_rows = db.execute(
        select(
            Prediction.decision,
            func.count(Prediction.id),
            func.avg(func.coalesce(Prediction.calibrated_score, Prediction.raw_score)),
        )
        .where(Prediction.company_id == company_id)
        .group_by(Prediction.decision)
    ).all()
    decision_counts = DecisionCounts()
    total_preds = 0
    weighted_score_sum = 0.0
    for decision, count, avg_dec in decision_rows:
        c = int(count or 0)
        total_preds += c
        if avg_dec is not None:
            weighted_score_sum += float(avg_dec) * c
        if decision == "approve":
            decision_counts.approve = c
        elif decision == "review":
            decision_counts.review = c
        elif decision == "block":
            decision_counts.block = c

    avg_score = (weighted_score_sum / total_preds) if total_preds else None

    latest_version = db.execute(
        select(Prediction.model_version)
        .where(Prediction.company_id == company_id)
        .order_by(desc(Prediction.created_at))
        .limit(1)
    ).scalar_one_or_none()

    # ----- Top-10 risky transactions (company-filtered) -----
    risky_q = (
        select(Prediction, Transaction)
        .join(Transaction, Transaction.id == Prediction.transaction_id)
        .where(Transaction.company_id == company_id)
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

    # Model-flagged rate — reflects what the model routed to review or block.
    # This is the meaningful KPI when most transactions are still PENDING
    # (ground-truth label only arrives on chargeback 30–60 days later).
    model_flagged_count = decision_counts.review + decision_counts.block
    model_flagged_rate = (model_flagged_count / total_preds) if total_preds else 0.0

    return MetricsSummary(
        total_transactions=total_txns,
        total_predictions=total_preds,
        fraud_count=fraud_count,
        fraud_rate=fraud_rate,
        model_flagged_count=model_flagged_count,
        model_flagged_rate=model_flagged_rate,
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
