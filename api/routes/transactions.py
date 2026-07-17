"""GET /api/transactions endpoints — list + detail with filters. Company-scoped."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, aliased, selectinload

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company
from api.schemas.transactions import (
    PaginatedTransactions,
    PredictionSummary,
    TransactionDetail,
    TransactionSummary,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=PaginatedTransactions)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    decision: Optional[str] = Query(None, pattern="^(approve|review|block)$"),
    min_score: Optional[float] = Query(None, ge=0, le=1),
    max_score: Optional[float] = Query(None, ge=0, le=1),
    is_fraud: Optional[bool] = None,
    product_cd: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Paginated + filterable list of transactions scoped to the caller's company."""
    # Multi-tenancy: only return transactions from the caller's company
    q = select(Transaction).where(Transaction.company_id == current_user.company_id)

    if min_amount is not None:
        q = q.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.where(Transaction.amount <= max_amount)
    if is_fraud is not None:
        q = q.where(Transaction.is_fraud == is_fraud)
    if product_cd is not None:
        q = q.where(Transaction.product_cd == product_cd)

    if decision or (min_score is not None) or (max_score is not None):
        q = q.join(Prediction, Transaction.id == Prediction.transaction_id)
        if decision:
            q = q.where(Prediction.decision == decision)
        if min_score is not None:
            q = q.where(
                func.coalesce(Prediction.calibrated_score, Prediction.raw_score) >= min_score
            )
        if max_score is not None:
            q = q.where(
                func.coalesce(Prediction.calibrated_score, Prediction.raw_score) <= max_score
            )
        q = q.distinct()

    total = db.execute(
        select(func.count()).select_from(q.subquery())
    ).scalar_one()

    q = q.order_by(desc(Transaction.created_at))
    q = q.offset((page - 1) * page_size).limit(page_size)

    rows = db.execute(q).scalars().all()

    # Fetch the latest prediction per transaction in ONE query rather than
    # sorting each row's `predictions` list in Python. Uses a correlated
    # subquery selecting the MAX(created_at) per transaction_id.
    txn_ids = [t.id for t in rows]
    latest_pred_by_txn: dict[int, Prediction] = {}
    if txn_ids:
        latest_ts_sq = (
            select(
                Prediction.transaction_id.label("tid"),
                func.max(Prediction.created_at).label("mts"),
            )
            .where(Prediction.transaction_id.in_(txn_ids))
            .group_by(Prediction.transaction_id)
            .subquery()
        )
        pred_rows = db.execute(
            select(Prediction).join(
                latest_ts_sq,
                and_(
                    Prediction.transaction_id == latest_ts_sq.c.tid,
                    Prediction.created_at == latest_ts_sq.c.mts,
                ),
            )
        ).scalars().all()
        for p in pred_rows:
            latest_pred_by_txn[p.transaction_id] = p

    items = []
    for txn in rows:
        latest_pred = latest_pred_by_txn.get(txn.id)
        items.append(TransactionSummary(
            id=txn.id,
            external_id=txn.external_id,
            transaction_dt=txn.transaction_dt,
            amount=txn.amount,
            card1=txn.card1,
            product_cd=txn.product_cd,
            p_emaildomain=txn.p_emaildomain,
            device_type=txn.device_type,
            is_fraud=txn.is_fraud,
            created_at=txn.created_at,
            latest_score=(
                latest_pred.calibrated_score if latest_pred and latest_pred.calibrated_score is not None
                else latest_pred.raw_score if latest_pred else None
            ),
            latest_decision=latest_pred.decision if latest_pred else None,
            latest_rules_triggered=(
                latest_pred.rules_triggered
                if latest_pred and latest_pred.rules_triggered else None
            ),
        ))

    return PaginatedTransactions(
        total=total, page=page, page_size=page_size, items=items,
    )


@router.get("/{txn_id}", response_model=TransactionDetail)
def get_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Full detail — only accessible if the transaction belongs to the caller's company."""
    txn = db.execute(
        select(Transaction)
        .where(Transaction.id == txn_id)
        .where(Transaction.company_id == current_user.company_id)  # Enforce isolation
        .options(selectinload(Transaction.predictions))
    ).scalar_one_or_none()

    if txn is None:
        raise HTTPException(404, f"Transaction {txn_id} not found")

    preds = [PredictionSummary.model_validate(p) for p in
             sorted(txn.predictions, key=lambda p: p.created_at, reverse=True)]

    return TransactionDetail(
        id=txn.id,
        external_id=txn.external_id,
        transaction_dt=txn.transaction_dt,
        amount=txn.amount,
        card1=txn.card1,
        card4=txn.card4,
        card6=txn.card6,
        product_cd=txn.product_cd,
        addr1=txn.addr1,
        p_emaildomain=txn.p_emaildomain,
        device_type=txn.device_type,
        device_info=txn.device_info,
        raw_features=txn.raw_features,
        is_fraud=txn.is_fraud,
        created_at=txn.created_at,
        predictions=preds,
    )
