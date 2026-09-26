import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_signup_and_duplicate_email(client: AsyncClient) -> None:
    payload = {"email": "new@example.com", "password": "StrongPassword123", "full_name": "New Patient"}
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]
    assert "password" not in response.json()
    assert "password_hash" not in response.json()

    duplicate = await client.post("/auth/signup", json=payload)
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_login_and_invalid_password(client: AsyncClient) -> None:
    await client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "StrongPassword123", "full_name": "Login User"},
    )
    success = await client.post(
        "/auth/login", json={"email": "login@example.com", "password": "StrongPassword123"}
    )
    assert success.status_code == 200
    assert success.json()["token_type"] == "bearer"
    assert success.json()["access_token"]

    failure = await client.post("/auth/login", json={"email": "login@example.com", "password": "WrongPassword123"})
    assert failure.status_code == 401


@pytest.mark.asyncio
async def test_protected_booking_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/bookings/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_openapi_uses_bearer_auth_for_json_login(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schemes = response.json()["components"]["securitySchemes"]
    assert schemes["HTTPBearer"]["type"] == "http"
    assert schemes["HTTPBearer"]["scheme"] == "bearer"
