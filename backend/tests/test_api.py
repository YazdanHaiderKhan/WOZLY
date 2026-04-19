"""API integration tests — auth endpoints."""
import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_register_and_login(client):
    """Full registration + login flow."""
    # Register
    resp = await client.post("/auth/register", json={
        "email": "test@wozly.dev", "password": "testpass123", "name": "Test User"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data

    # Login with same credentials
    resp2 = await client.post("/auth/login", json={
        "email": "test@wozly.dev", "password": "testpass123"
    })
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client):
    await client.post("/auth/register", json={
        "email": "dup@wozly.dev", "password": "pass12345", "name": "User One"
    })
    resp = await client.post("/auth/register", json={
        "email": "dup@wozly.dev", "password": "pass12345", "name": "User Two"
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invalid_credentials_rejected(client):
    resp = await client.post("/auth/login", json={
        "email": "nobody@wozly.dev", "password": "wrongpass"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token(client):
    resp = await client.get("/user/me")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_token_refresh(client):
    reg = await client.post("/auth/register", json={
        "email": "refresh@wozly.dev", "password": "pass12345", "name": "Refresh User"
    })
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_health_endpoint(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
