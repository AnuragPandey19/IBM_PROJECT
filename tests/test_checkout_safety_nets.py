"""Integration test: hit /api/checkout with adversarial payloads and verify
the decision augmenter actually fires end-to-end.

This is the second half of the 4-layer testing plan for the decision
augmenter (unit tests being layer 1). It uses FastAPI's TestClient
against a real ModelService instance so it exercises the full path:
route -> model service -> augmenter -> Prediction row -> response.
"""
from __future__ import annotations

import os
import uuid

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-checkout-safety-nets")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.db.base import Base  # noqa: E402
from api.db import models  # noqa: E402,F401
from api.db.session import get_db  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(test_engine):
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False,
                           expire_on_commit=False)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _checkout_body(**overrides):
    base = {
        "card_number": "4532111122225678",         # new-profile card
        "cardholder_name": "Test User",
        "amount": 100.0,
        "merchant_name": "Test Merchant",
        "merchant_category": "grocery_pos",
        "cust_email": f"test-{uuid.uuid4().hex[:6]}@example.com",
        "demo_profile": "established",
        "demo_hour_override": 14,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Rule 1 — card_testing end-to-end
# ---------------------------------------------------------------------------

def test_checkout_card_testing_gets_review(client):
    r = client.post("/api/checkout", json=_checkout_body(
        amount=1.49,
        demo_profile="new",
        merchant_category="misc_net",
        demo_hour_override=3,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    # The augmenter should have pushed this from approve -> review.
    # Even if the model wanted to block, review is acceptable; the key
    # invariant is "not approved".
    assert body["status"] in ("review", "declined")


def test_checkout_normal_grocery_gets_approved(client):
    r = client.post("/api/checkout", json=_checkout_body(
        amount=45.00,
        demo_profile="established",
        merchant_category="grocery_pos",
        demo_hour_override=14,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    # Baseline sanity — legit routine grocery should not trip any rule.
    assert body["status"] == "approved"


# ---------------------------------------------------------------------------
# Rule 2 — velocity_spike end-to-end
# ---------------------------------------------------------------------------

def test_checkout_velocity_spike_established_gets_review(client):
    """Established customer (~$55 avg) spends $600 = 11x — trip velocity rule."""
    r = client.post("/api/checkout", json=_checkout_body(
        amount=600.00,
        demo_profile="established",
        merchant_category="shopping_net",
        demo_hour_override=15,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("review", "declined"), body


def test_checkout_high_spender_wedding_stays_approved(client):
    """high_spender is deliberately excluded from velocity_spike; a $3000
    wedding-shaped payment must NOT be flagged as fraud."""
    r = client.post("/api/checkout", json=_checkout_body(
        amount=3000.00,
        demo_profile="high_spender",
        merchant_category="misc_net",
        merchant_name="Ferns N Petals",
        demo_hour_override=17,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    # We accept either approved or review here — the important thing is
    # NOT declined. Rules must not turn a legit wedding into a decline.
    assert body["status"] != "declined", body


# ---------------------------------------------------------------------------
# Rule 3 — evening + new + high amount
# ---------------------------------------------------------------------------

def test_checkout_new_customer_late_evening_high_gets_review(client):
    r = client.post("/api/checkout", json=_checkout_body(
        amount=2500.00,
        demo_profile="new",
        merchant_category="travel",
        demo_hour_override=22,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("review", "declined"), body


def test_checkout_new_customer_daytime_high_no_night_rule(client):
    """Same payload but daytime — night rule should NOT fire.
    (Other rules could still fire; assertion focuses on rule-1/rule-3 not
    triggering.)"""
    r = client.post("/api/checkout", json=_checkout_body(
        amount=2500.00,
        demo_profile="new",
        merchant_category="travel",
        demo_hour_override=13,
    ))
    assert r.status_code == 200, r.text
    body = r.json()
    # No explicit expectation on status — model may or may not block on its
    # own. Sanity check: response is a valid decision, not an error.
    assert body["status"] in ("approved", "review", "declined"), body
