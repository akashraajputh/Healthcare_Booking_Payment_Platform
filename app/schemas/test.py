from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=4000)


class TestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    is_active: bool


class CentreTestCreate(BaseModel):
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CentreTestRead(BaseModel):
    test: TestRead
    price: Decimal
