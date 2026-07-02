"""Auth flow tests: register + login + protected route."""
import uuid
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def _unique_email():
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def test_register_then_login_flow():
    email = _unique_email()
    password = "supersecret123"
    r = client.post("/auth/register", json={
        "email": email, "password": password,
        "full_name": "Test User", "role": "analyst",
    })
    assert r.status_code == 201, r.text
    user = r.json()
    assert user["email"] == email
    assert user["role"] == "analyst"
    assert user["is_active"] is True

    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    tok = r.json()
    assert tok["token_type"] == "bearer"
    token = tok["access_token"]
    assert token

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == email


def test_login_with_wrong_password_rejected():
    email = _unique_email()
    client.post("/auth/register", json={"email": email, "password": "correctpass1"})
    r = client.post("/auth/login", json={"email": email, "password": "wrongpass1"})
    assert r.status_code == 401


def test_duplicate_registration_rejected():
    email = _unique_email()
    r1 = client.post("/auth/register", json={"email": email, "password": "pass12345"})
    assert r1.status_code == 201
    r2 = client.post("/auth/register", json={"email": email, "password": "pass12345"})
    assert r2.status_code == 409


def test_me_without_token_rejected():
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_bad_token_rejected():
    r = client.get("/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401
