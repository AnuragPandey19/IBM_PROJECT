"""Basic smoke tests for the API scaffold. Run with: pytest api/tests/"""
from fastapi.testclient import TestClient

from api.main import app


client = TestClient(app)


def test_root_returns_metadata():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "app" in data
    assert "version" in data


def test_health_check_ok():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "timestamp" in data


def test_readiness_returns_check_result():
    r = client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert "ready" in data
    assert "checks" in data
    assert "database" in data["checks"]
