"""Tests for the transactions endpoints."""
import uuid
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def _get_token():
    email = f"txn-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "txntestpass123", "role": "analyst",
    })
    r = client.post("/auth/login", json={"email": email, "password": "txntestpass123"})
    return r.json()["access_token"]


def test_transactions_requires_auth():
    r = client.get("/api/transactions")
    assert r.status_code == 401


def test_list_transactions_empty_or_populated():
    token = _get_token()
    r = client.get(
        "/api/transactions",
        headers={"Authorization": f"Bearer {token}"},
        params={"page": 1, "page_size": 10},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "total" in data
    assert "items" in data
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert isinstance(data["items"], list)


def test_transaction_not_found():
    token = _get_token()
    r = client.get(
        "/api/transactions/999999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_list_transactions_invalid_decision_rejected():
    token = _get_token()
    r = client.get(
        "/api/transactions",
        headers={"Authorization": f"Bearer {token}"},
        params={"decision": "bogus"},
    )
    assert r.status_code == 422
