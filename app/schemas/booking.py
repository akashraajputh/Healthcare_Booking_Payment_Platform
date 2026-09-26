from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class BookingCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{
            "centre_id": 1,
            "test_id": 2,
            "appointment_at": "2026-10-01T10:30:00Z",
        }]},
    )

    centre_id: int = Field(gt=0)
    test_id: int = Field(gt=0)
    appointment_at: datetime

    @field_validator("appointment_at")
    @classmethod
    def appointment_must_be_future(cls, value: datetime) -> datetime:
        from datetime import UTC, datetime as DateTime

        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        if value <= DateTime.now(UTC):
            raise ValueError("appointment_at must be in the future")
        return value


class BookingRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{
            "id": 101,
            "centre_id": 1,
            "centre_name": "Apollo Diagnostics",
            "test_id": 2,
            "test_name": "CBC",
            "appointment_at": "2026-10-01T10:30:00Z",
            "amount": "500.00",
            "status": "PENDING",
            "created_at": "2026-09-26T12:00:00Z",
        }]},
    )

    id: int
    centre_id: int
    centre_name: str
    test_id: int
    test_name: str
    appointment_at: datetime
    amount: Decimal
    status: BookingStatus
    created_at: datetime
