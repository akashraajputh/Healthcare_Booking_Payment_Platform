import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.payment import PaymentStatus
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentRead, WebhookRequest, WebhookResponse
from app.services.payment_service import process_webhook, simulate_payment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_mock_payment(
    payload: PaymentCreate,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PaymentRead:
    outcome = PaymentStatus(payload.simulate.value)
    payment = await simulate_payment(session, user, payload.booking_id, outcome)
    logger.info("mock_payment_processed", extra={"booking_id": payment.booking_id, "payment_status": payment.status.value})
    return PaymentRead.model_validate(payment)


@router.post("/webhook/", response_model=WebhookResponse)
async def payment_webhook(payload: WebhookRequest, session: AsyncSession = Depends(get_db)) -> WebhookResponse:
    logger.info("payment_webhook_received", extra={"event_id": payload.event_id, "event_type": payload.event_type})
    result = await process_webhook(
        session,
        payload.event_id,
        payload.event_type,
        payload.provider_payment_id,
        payload.booking_id,
        payload.amount,
    )
    if result["status"] == "duplicate":
        logger.info("payment_webhook_duplicate", extra={"event_id": payload.event_id})
    return WebhookResponse(**result)
