"""Multi-tenancy isolation tests.

Highest-value tests in the project: a single cross-tenant leak would destroy
CHIMERA-FD's credibility as a B2B product. Every read path that touches
Transaction, Prediction, or company-scoped analytics MUST filter by
`company_id`, and this suite exercises that guarantee end-to-end via the
FastAPI TestClient.

Run with:  pytest tests/test_multi_tenancy.py -v

Design notes
------------
- We build an isolated in-memory SQLite DB per test (no shared state, no need
  to nuke `data/api.db`), then override the get_db dependency to point the app
  at it. StaticPool + a single shared connection is REQUIRED because
  `sqlite:///:memory:` gives each new connection its own empty database.
- Two companies (Acme + Globex) are seeded with distinct users + transactions.
  Each request is made with only one company's JWT, and we assert the response
  never contains the other company's data.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Force a predictable env BEFORE importing the app so config caches don't
# accidentally pick up the developer's local .env.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-multi-tenancy-not-for-prod")

from api.db.base import Base                       # noqa: E402
from api.db import models                          # noqa: E402,F401 (registers tables)
from api.db.models import Company, Prediction, Transaction, User  # noqa: E402
from api.db.session import get_db                  # noqa: E402
from api.main import app                           # noqa: E402
from api.security import hash_password, create_access_token  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_engine():
    """One shared in-memory SQLite engine per test.

    StaticPool + a single connection is required because `sqlite:///:memory:`
    gives each new connection its OWN empty DB - without StaticPool, the
    seeding session and the app's per-request sessions would see different
    databases and the app would report `no such table: users`.
    """
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
def db_session(test_engine):
    """A short-lived session for seeding fixtures."""
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False,
                           expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(test_engine, db_session):
    """TestClient wired to the shared in-memory engine."""
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False,
                           expire_on_commit=False)

    def _override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def two_tenant_world(db_session):
    """Seed two companies, one user each, and 3+3 transactions."""
    acme = Company(name="Acme Corp", industry="fintech", is_active=True)
    globex = Company(name="Globex Inc", industry="retail", is_active=True)
    db_session.add_all([acme, globex])
    db_session.flush()

    acme_user = User(
        email=f"alice-{uuid.uuid4().hex[:6]}@acme.test",
        hashed_password=hash_password("password123"),
        full_name="Alice Acme",
        role="analyst",
        is_active=True,
        company_id=acme.id,
    )
    globex_user = User(
        email=f"bob-{uuid.uuid4().hex[:6]}@globex.test",
        hashed_password=hash_password("password123"),
        full_name="Bob Globex",
        role="analyst",
        is_active=True,
        company_id=globex.id,
    )
    db_session.add_all([acme_user, globex_user])
    db_session.flush()

    acme_txns = []
    for i in range(3):
        t = Transaction(
            external_id=f"ACME-{i:03d}",
            amount=100.0 + i,
            company_id=acme.id,
        )
        db_session.add(t)
        acme_txns.append(t)

    globex_txns = []
    for i in range(3):
        t = Transaction(
            external_id=f"GLOBEX-{i:03d}",
            amount=200.0 + i,
            company_id=globex.id,
        )
        db_session.add(t)
        globex_txns.append(t)

    db_session.flush()

    # One prediction per txn so /transactions detail endpoints have something
    for txn in acme_txns + globex_txns:
        p = Prediction(
            transaction_id=txn.id,
            raw_score=0.42,
            calibrated_score=0.42,
            decision="review",
            model_version="test-1.0",
            company_id=txn.company_id,
        )
        db_session.add(p)

    db_session.commit()

    return {
        "acme": acme,
        "globex": globex,
        "acme_user": acme_user,
        "globex_user": globex_user,
        "acme_txns": acme_txns,
        "globex_txns": globex_txns,
    }


def _auth_header(user: User) -> dict:
    """Sign a JWT for `user` using the same helper the app uses."""
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Isolation tests
# ---------------------------------------------------------------------------

def test_transactions_list_only_returns_own_company(client, two_tenant_world):
    """GET /api/transactions must never show another tenant's rows."""
    w = two_tenant_world

    r = client.get("/api/transactions?page=1&page_size=100",
                   headers=_auth_header(w["acme_user"]))
    assert r.status_code == 200, r.text
    ext_ids = [row["external_id"] for row in r.json()["items"]]
    assert all(x.startswith("ACME-") for x in ext_ids), (
        f"Acme user saw non-Acme transactions: {ext_ids}"
    )
    assert len(ext_ids) == 3

    r = client.get("/api/transactions?page=1&page_size=100",
                   headers=_auth_header(w["globex_user"]))
    assert r.status_code == 200, r.text
    ext_ids = [row["external_id"] for row in r.json()["items"]]
    assert all(x.startswith("GLOBEX-") for x in ext_ids), (
        f"Globex user saw non-Globex transactions: {ext_ids}"
    )
    assert len(ext_ids) == 3


def test_transaction_detail_forbids_cross_tenant_access(client, two_tenant_world):
    """GET /api/transactions/{id} must 404 for another tenant's row.

    404 (not 403) is the correct answer - we don't want to leak the existence
    of an ID belonging to another tenant. Either 403 or 404 is acceptable as
    long as the door is shut.
    """
    w = two_tenant_world
    globex_txn_id = w["globex_txns"][0].id

    r = client.get(f"/api/transactions/{globex_txn_id}",
                   headers=_auth_header(w["acme_user"]))
    assert r.status_code in (403, 404), (
        f"Acme user was allowed to see Globex txn {globex_txn_id}: "
        f"HTTP {r.status_code} body={r.text[:200]}"
    )


def test_metrics_are_company_scoped(client, two_tenant_world):
    """/api/metrics/summary KPIs must aggregate only over the caller's company."""
    w = two_tenant_world

    r = client.get("/api/metrics/summary", headers=_auth_header(w["acme_user"]))
    assert r.status_code == 200, r.text
    acme_body = r.json()

    r = client.get("/api/metrics/summary", headers=_auth_header(w["globex_user"]))
    assert r.status_code == 200, r.text
    globex_body = r.json()

    # Both tenants have 3 transactions each. If aggregation leaked, one side
    # would see 6.
    assert acme_body.get("total_transactions") == 3, acme_body
    assert globex_body.get("total_transactions") == 3, globex_body


def test_analytics_timeseries_is_company_scoped(client, two_tenant_world):
    """/api/analytics/timeseries totals must not include other tenants."""
    w = two_tenant_world

    r = client.get("/api/analytics/timeseries?period=monthly&limit=12",
                   headers=_auth_header(w["acme_user"]))
    assert r.status_code == 200, r.text
    totals = r.json()["totals"]
    # Acme has 3 rows totaling 100+101+102 = 303
    assert totals["transactions"] == 3
    assert abs(totals["volume"] - 303.0) < 0.01, totals


def test_unauthenticated_requests_are_rejected(client, two_tenant_world):
    """No JWT => 401 on any company-scoped endpoint. Belt-and-suspenders test
    to make sure someone doesn't accidentally drop the auth dependency."""
    for path in (
        "/api/transactions",
        "/api/metrics/summary",
        "/api/analytics/timeseries",
        "/api/notifications",
    ):
        r = client.get(path)
        assert r.status_code == 401, (
            f"{path} was reachable without a JWT - HTTP {r.status_code}"
        )


def test_user_without_company_gets_403(client, db_session):
    """A user whose company_id is NULL cannot use company-scoped endpoints.

    require_company enforces this - regression test guards it.
    """
    orphan = User(
        email=f"orphan-{uuid.uuid4().hex[:6]}@nowhere.test",
        hashed_password=hash_password("password123"),
           role="analyst",
        is_active=True,
        company_id=None,
    )
    db_session.add(orphan)
    db_session.commit()

    r = client.get("/api/transactions", headers=_auth_header(orphan))
    assert r.status_code == 403, r.text
