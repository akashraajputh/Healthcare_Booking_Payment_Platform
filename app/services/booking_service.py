from datetime import UTC, datetime
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.booking import Booking, BookingStatus
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User

logger = logging.getLogger(__name__)


async def create_booking(session: AsyncSession, user: User, centre_id: int, test_id: int, appointment_at: datetime) -> Booking:
    centre_test = await session.scalar(
        select(CentreTest)
        .join(Centre, Centre.id == CentreTest.centre_id)
        .join(DiagnosticTest, DiagnosticTest.id == CentreTest.test_id)
        .where(
            CentreTest.centre_id == centre_id,
            CentreTest.test_id == test_id,
            Centre.is_active.is_(True),
            DiagnosticTest.is_active.is_(True),
        )
    )
    if centre_test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre/test offering not found")
    if appointment_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Appointment must be in the future")

    booking = Booking(
        user_id=user.id,
        centre_id=centre_id,
        test_id=test_id,
        appointment_at=appointment_at,
        amount=centre_test.price,
        status=BookingStatus.PENDING,
    )
    session.add(booking)
    await session.commit()
    logger.info(
        "booking_created",
        extra={"booking_id": booking.id, "user_id": user.id, "centre_id": centre_id, "test_id": test_id},
    )
    booking = await get_owned_booking(session, booking.id, user.id)
    return booking


async def get_owned_booking(session: AsyncSession, booking_id: int, user_id: int) -> Booking:
    booking = await session.scalar(
        select(Booking)
        .options(joinedload(Booking.centre), joinedload(Booking.test))
        .where(Booking.id == booking_id, Booking.user_id == user_id)
    )
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


async def list_user_bookings(session: AsyncSession, user_id: int) -> list[Booking]:
    result = await session.scalars(
        select(Booking)
        .options(joinedload(Booking.centre), joinedload(Booking.test))
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
    )
    return list(result.unique().all())


async def cancel_booking(session: AsyncSession, booking_id: int, user_id: int) -> Booking:
    booking = await session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user_id)
        .with_for_update()
    )
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.status != BookingStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending bookings can be cancelled")
    booking.status = BookingStatus.CANCELLED
    await session.commit()
    return await get_owned_booking(session, booking_id, user_id)
