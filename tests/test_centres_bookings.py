from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_catalog_and_public_retrieval(
    client: AsyncClient, admin_user: dict[str, object], catalog: dict[str, int]
) -> None:
    headers = {"Authorization": f"Bearer {admin_user['token']}"}
    centres = await client.get("/centres/")
    tests = await client.get("/tests/")
    offerings = await client.get(f"/centres/{catalog['centre_id']}/tests")
    assert centres.status_code == tests.status_code == offerings.status_code == 200
    assert centres.json()[0]["name"] == "EVE Central Lab"
    assert tests.json()[0]["name"] == "CBC"
    assert offerings.json()[0]["price"] == "500.00"

    denied = await client.post("/centres/", json={"name": "Nope", "location": "Nowhere"})
    assert denied.status_code == 401
    regular = await client.post("/auth/signup", json={
        "email": "regular@example.com", "password": "StrongPassword123", "full_name": "Regular User"
    })
    token = (await client.post("/auth/login", json={
        "email": "regular@example.com", "password": "StrongPassword123"
    })).json()["access_token"]
    denied = await client.post(
        "/centres/", json={"name": "Nope", "location": "Nowhere"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_booking_uses_catalog_price_and_enforces_ownership_and_cancel(
    client: AsyncClient, registered_user: dict[str, object], catalog: dict[str, int]
) -> None:
    headers = {"Authorization": f"Bearer {registered_user['token']}"}
    payload = {
        **catalog,
        "appointment_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "amount": "1.00",
    }
    response = await client.post("/bookings/", json=payload, headers=headers)
    assert response.status_code == 422
    payload.pop("amount")
    response = await client.post("/bookings/", json=payload, headers=headers)
    assert response.status_code == 201
    booking = response.json()
    assert booking["amount"] == "500.00"
    assert booking["status"] == "PENDING"

    stranger = await client.post("/auth/signup", json={
        "email": "stranger@example.com", "password": "StrongPassword123", "full_name": "Stranger"
    })
    stranger_token = (await client.post("/auth/login", json={
        "email": "stranger@example.com", "password": "StrongPassword123"
    })).json()["access_token"]
    hidden = await client.get(
        f"/bookings/{booking['id']}", headers={"Authorization": f"Bearer {stranger_token}"}
    )
    assert hidden.status_code == 404

    cancelled = await client.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    repeated = await client.post(f"/bookings/{booking['id']}/cancel", headers=headers)
    assert repeated.status_code == 409


@pytest.mark.asyncio
async def test_booking_requires_valid_centre_test_offer(
    client: AsyncClient, registered_user: dict[str, object], catalog: dict[str, int]
) -> None:
    headers = {"Authorization": f"Bearer {registered_user['token']}"}
    payload = {
        "centre_id": catalog["centre_id"],
        "test_id": 9999,
        "appointment_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
    }
    response = await client.post("/bookings/", json=payload, headers=headers)
    assert response.status_code == 404
