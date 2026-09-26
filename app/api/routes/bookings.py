from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingRead
from app.services.booking_service import cancel_booking, create_booking, get_owned_booking, list_user_bookings

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking_endpoint(
    payload: BookingCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    return await create_booking(session, user, payload.centre_id, payload.test_id, payload.appointment_at)


@router.get("/", response_model=list[BookingRead])
async def list_bookings(
    session: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Booking]:
    return await list_user_bookings(session, user.id)


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(
    booking_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    return await get_owned_booking(session, booking_id, user.id)


@router.post("/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking_endpoint(
    booking_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Booking:
    return await cancel_booking(session, booking_id, user.id)
