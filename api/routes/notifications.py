"""GET /api/notifications — derived from recent significant events."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from api.db.models import Prediction, Transaction, User
from api.db.session import get_db
from api.dependencies.auth import require_company

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["notifications"])


class Notification(BaseModel):
    id: str
    type: str  # "high_risk" | "review_queue" | "block" | "new_member"
    title: str
    body: str
    severity: str  # "info" | "warning" | "critical"
    created_at: datetime
    link: Optional[str] = None


class NotificationList(BaseModel):
    items: list[Notification]
    unread_count: int


@router.get("/notifications", response_model=NotificationList)
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_company),
):
    """Return derived notifications from recent activity in the caller's company.

    We synthesize notifications from real predictions:
      - BLOCK decisions in the last 7 days -> critical alerts
      - REVIEW decisions in the last 7 days -> warnings
      - New team members joined in the last 30 days -> info

    In a full production system these would live in a dedicated notifications
    table with per-user read state. For the current phase we derive them at
    query time and cap at 20 items.
    """
    company_id = current_user.company_id
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    notifs: list[Notification] = []

    # Recent BLOCK predictions -> critical
    blocks = db.execute(
        select(Prediction)
        .where(Prediction.company_id == company_id)
        .where(Prediction.decision == "block")
        .where(Prediction.created_at >= seven_days_ago)
        .options(selectinload(Prediction.transaction))
        .order_by(desc(Prediction.created_at))
        .limit(5)
    ).scalars().all()

    for p in blocks:
        amt = p.transaction.amount if p.transaction else 0
        notifs.append(Notification(
            id=f"pred-block-{p.id}",
            type="block",
            title=f"High-confidence fraud blocked",
            body=f"Transaction #{p.transaction_id} (${amt:.0f}) auto-blocked at score {p.calibrated_score or p.raw_score:.3f}",
            severity="critical",
            created_at=p.created_at,
            link=f"/transaction?id={p.transaction_id}",
        ))

    # Recent REVIEW predictions -> warnings (sample a few high-scored ones)
    reviews = db.execute(
        select(Prediction)
        .where(Prediction.company_id == company_id)
        .where(Prediction.decision == "review")
        .where(Prediction.created_at >= seven_days_ago)
        .options(selectinload(Prediction.transaction))
        .order_by(desc(Prediction.calibrated_score))
        .limit(8)
    ).scalars().all()

    for p in reviews:
        amt = p.transaction.amount if p.transaction else 0
        notifs.append(Notification(
            id=f"pred-review-{p.id}",
            type="review_queue",
            title=f"Transaction awaiting review",
            body=f"#{p.transaction_id} (${amt:.0f}) flagged at score {p.calibrated_score or p.raw_score:.3f}",
            severity="warning",
            created_at=p.created_at,
            link=f"/transaction?id={p.transaction_id}",
        ))

    # New team members
    new_members = db.execute(
        select(User)
        .where(User.company_id == company_id)
        .where(User.id != current_user.id)
        .where(User.created_at >= thirty_days_ago)
        .order_by(desc(User.created_at))
        .limit(5)
    ).scalars().all()

    for u in new_members:
        notifs.append(Notification(
            id=f"user-joined-{u.id}",
            type="new_member",
            title=f"New team member",
            body=f"{u.full_name or u.email} joined as {u.role}",
            severity="info",
            created_at=u.created_at,
            link=None,
        ))

    # Sort combined list by timestamp desc
    notifs.sort(key=lambda n: n.created_at, reverse=True)
    notifs = notifs[:20]

    return NotificationList(items=notifs, unread_count=len(notifs))
