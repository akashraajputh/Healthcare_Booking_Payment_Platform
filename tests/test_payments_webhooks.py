import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment
from app.models.webhook_event import WebhookEvent


async def create_booking(client: AsyncClient, token: str, catalog: dict[str, int]) -> dict[str, object]:
    response = await client.post(
        "/bookings/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            **catalog,
            "appointment_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_mock_payment_success_failure_and_duplicate(
    client: AsyncClient, registered_user: dict[str, object], catalog: dict[str, int]
) -> None:
    headers = {"Authorization": f"Bearer {registered_user['token']}"}
    successful_booking = await create_booking(client, registered_user["token"], catalog)
    success = await client.post(
        "/payments/", headers=headers,
        json={"booking_id": successful_booking["id"], "simulate": "SUCCESS"},
    )
    assert success.status_code == 201
    assert success.json()["amount"] == "500.00"
    assert (await client.get(f"/bookings/{successful_booking['id']}", headers=headers)).json()["status"] == "CONFIRMED"
    duplicate = await client.post(
        "/payments/", headers=headers,
        json={"booking_id": successful_booking["id"], "simulate": "SUCCESS"},
    )
    assert duplicate.status_code == 409

    failed_booking = await create_booking(client, registered_user["token"], catalog)
    failed = await client.post(
        "/payments/", headers=headers,
        json={"booking_id": failed_booking["id"], "simulate": "FAILED"},
    )
    assert failed.status_code == 201
    assert (await client.get(f"/bookings/{failed_booking['id']}", headers=headers)).json()["status"] == "FAILED"


@pytest.mark.asyncio
async def test_webhook_is_idempotent_even_when_requests_overlap(
    client: AsyncClient,
    registered_user: dict[str, object],
    catalog: dict[str, int],
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    booking = await create_booking(client, registered_user["token"], catalog)
    payload = {
        "event_id": "evt_concurrent_001",
        "event_type": "payment.success",
        "provider_payment_id": "pay_concurrent_001",
        "booking_id": booking["id"],
        "amount": "500.00",
    }
    first, second = await asyncio.gather(
        client.post("/payments/webhook/", json=payload),
        client.post("/payments/webhook/", json=payload),
    )
    assert first.status_code == second.status_code == 200
    assert {first.json()["status"], second.json()["status"]} == {"processed", "duplicate"}

    async with test_session_factory() as session:
        payment_count = await session.scalar(select(func.count()).select_from(Payment))
        event_count = await session.scalar(select(func.count()).select_from(WebhookEvent))
        db_booking = await session.get(Booking, booking["id"])
        assert payment_count == event_count == 1
        assert db_booking is not None and db_booking.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_webhook_failure_and_validation(
    client: AsyncClient, registered_user: dict[str, object], catalog: dict[str, int]
) -> None:
    booking = await create_booking(client, registered_user["token"], catalog)
    base = {
        "event_id": "evt_failure_001",
        "event_type": "payment.failed",
        "provider_payment_id": "pay_failure_001",
        "booking_id": booking["id"],
        "amount": "500.00",
    }
    failed = await client.post("/payments/webhook/", json=base)
    assert failed.status_code == 200
    assert (await client.get(f"/bookings/{booking['id']}", headers={
        "Authorization": f"Bearer {registered_user['token']}"
    })).json()["status"] == "FAILED"

    invalid_id = await client.post("/payments/webhook/", json={**base, "event_id": "bad id"})
    assert invalid_id.status_code == 422

    other_booking = await create_booking(client, registered_user["token"], catalog)
    mismatch = await client.post("/payments/webhook/", json={
        **base, "event_id": "evt_mismatch_001", "provider_payment_id": "pay_mismatch_001",
        "booking_id": other_booking["id"], "amount": "1.00",
    })
    assert mismatch.status_code == 409


@pytest.mark.asyncio
async def test_invalid_booking_webhook_rolls_back_event(
    client: AsyncClient,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post("/payments/webhook/", json={
        "event_id": "evt_unknown_booking_001",
        "event_type": "payment.success",
        "provider_payment_id": "pay_unknown_booking_001",
        "booking_id": 999999,
        "amount": "500.00",
    })
    assert response.status_code == 404
    async with test_session_factory() as session:
        event_count = await session.scalar(select(func.count()).select_from(WebhookEvent))
        payment_count = await session.scalar(select(func.count()).select_from(Payment))
        assert event_count == payment_count == 0


@pytest.mark.asyncio
async def test_distinct_late_webhook_cannot_overwrite_final_booking(
    client: AsyncClient,
    registered_user: dict[str, object],
    catalog: dict[str, int],
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    booking = await create_booking(client, registered_user["token"], catalog)
    first_event = {
        "event_id": "evt_first_success_001",
        "event_type": "payment.success",
        "provider_payment_id": "pay_first_success_001",
        "booking_id": booking["id"],
        "amount": "500.00",
    }
    first = await client.post("/payments/webhook/", json=first_event)
    late = await client.post("/payments/webhook/", json={
        **first_event,
        "event_id": "evt_late_failure_001",
        "event_type": "payment.failed",
        "provider_payment_id": "pay_late_failure_001",
    })
    assert first.status_code == late.status_code == 200
    assert first.json()["status"] == late.json()["status"] == "processed"

    async with test_session_factory() as session:
        db_booking = await session.get(Booking, booking["id"])
        payment_count = await session.scalar(select(func.count()).select_from(Payment))
        event_count = await session.scalar(select(func.count()).select_from(WebhookEvent))
        assert db_booking is not None and db_booking.status == BookingStatus.CONFIRMED
        assert payment_count == 1
        assert event_count == 2
