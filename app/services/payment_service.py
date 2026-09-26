from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User
from app.models.webhook_event import WebhookEvent


async def simulate_payment(session: AsyncSession, user: User, booking_id: int, outcome: PaymentStatus) -> Payment:
    try:
        booking = await session.scalar(
            select(Booking).where(Booking.id == booking_id, Booking.user_id == user.id).with_for_update()
        )
        if booking is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if booking.status != BookingStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Booking is not pending")
        payment = Payment(
            booking_id=booking.id,
            provider_payment_id=f"mock_{uuid4().hex}",
            amount=booking.amount,
            status=outcome,
        )
        session.add(payment)
        booking.status = BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED
        await session.commit()
        await session.refresh(payment)
        return payment
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A payment already exists for this booking") from None
    except HTTPException:
        await session.rollback()
        raise


async def process_webhook(session: AsyncSession, event_id: str, event_type: str, provider_payment_id: str, booking_id: int, amount) -> dict[str, str | bool]:
    dialect = session.bind.dialect.name if session.bind else ""
    insert_statement = pg_insert if dialect == "postgresql" else sqlite_insert if dialect == "sqlite" else None
    if insert_statement is None:
        raise RuntimeError("Webhook idempotency requires PostgreSQL or SQLite")

    try:
        async with session.begin():
            event_statement = (
                insert_statement(WebhookEvent)
                .values(event_id=event_id, event_type=event_type, processed=False)
                .on_conflict_do_nothing(index_elements=["event_id"])
                .returning(WebhookEvent.id)
            )
            event_pk = (await session.execute(event_statement)).scalar_one_or_none()
            if event_pk is None:
                return {"status": "duplicate", "processed": True}

            event = await session.get(WebhookEvent, event_pk)
            booking = await session.scalar(select(Booking).where(Booking.id == booking_id).with_for_update())
            if booking is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
            if amount != booking.amount:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment amount does not match booking")

            if booking.status == BookingStatus.PENDING:
                outcome = PaymentStatus.SUCCESS if event_type == "payment.success" else PaymentStatus.FAILED
                session.add(
                    Payment(
                        booking_id=booking.id,
                        provider_payment_id=provider_payment_id,
                        amount=booking.amount,
                        status=outcome,
                    )
                )
                booking.status = BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED
            event.processed = True
            event.processed_at = datetime.now(UTC)
            await session.flush()
        return {"status": "processed", "processed": True}
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment conflicts with an existing payment") from None
