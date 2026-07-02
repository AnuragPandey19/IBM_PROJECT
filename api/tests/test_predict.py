"""Tests for POST /api/predict."""
import uuid
from fastapi.testclient import TestClient
from api.main import app
from api.config import get_settings
import pytest

settings = get_settings()
client = TestClient(app)


def _skip_if_no_model():
    if not settings.stage1_model_path.exists():
        pytest.skip("Stage 1 model missing")
    if not settings.feature_pipeline_path.exists():
        pytest.skip("Feature pipeline missing")


def _get_token():
    email = f"predict-{uuid.uuid4().hex[:8]}@example.com"
    client.post("/auth/register", json={
        "email": email, "password": "predictpass123", "role": "analyst",
    })
    r = client.post("/auth/login", json={"email": email, "password": "predictpass123"})
    return r.json()["access_token"]


def test_predict_requires_auth():
    r = client.post("/api/predict", json={
        "TransactionDT": 86400, "TransactionAmt": 100.0,
    })
    assert r.status_code == 401


def test_predict_end_to_end():
    _skip_if_no_model()
    token = _get_token()
    unique_id = f"test-txn-{uuid.uuid4().hex[:12]}"
    r = client.post(
        "/api/predict",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "external_id": unique_id,
            "TransactionDT": 86400,
            "TransactionAmt": 250.50,
            "ProductCD": "W",
            "card1": 12345,
            "card4": "visa",
            "card6": "credit",
            "P_emaildomain": "gmail.com",
            "DeviceType": "desktop",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "transaction_id" in data
    assert "prediction_id" in data
    assert "raw_score" in data
    assert "calibrated_score" in data
    assert data["decision"] in ("approve", "review", "block")
    assert len(data["shap_top"]) == 5
    assert data["latency_ms"] >= 0
    for s in data["shap_top"]:
        assert "feature" in s
        assert "contribution" in s


def test_predict_validation_reject_negative_amount():
    token = _get_token()
    r = client.post(
        "/api/predict",
        headers={"Authorization": f"Bearer {token}"},
        json={"TransactionDT": 86400, "TransactionAmt": -50.0},
    )
    assert r.status_code == 422
