from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SimulatedPaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class PaymentCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"booking_id": 101, "simulate": "SUCCESS"}]})

    booking_id: int = Field(gt=0)
    simulate: SimulatedPaymentStatus


class PaymentRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{
            "id": 9,
            "booking_id": 101,
            "provider_payment_id": "mock_pay_123",
            "amount": "500.00",
            "status": "SUCCESS",
        }]},
    )

    id: int
    booking_id: int
    provider_payment_id: str | None
    amount: Decimal
    status: SimulatedPaymentStatus


class WebhookRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "event_id": "evt_123456",
        "event_type": "payment.success",
        "provider_payment_id": "pay_123",
        "booking_id": 101,
        "amount": "500.00",
    }]})

    event_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    event_type: str = Field(pattern=r"^payment\.(success|failed)$")
    provider_payment_id: str = Field(min_length=1, max_length=128)
    booking_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class WebhookResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "processed", "processed": True}]})

    status: str
    processed: bool
