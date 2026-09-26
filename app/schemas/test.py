from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TestCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "name": "CBC",
        "description": "Complete Blood Count",
    }]})

    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=4000)


class TestRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{
            "id": 2,
            "name": "CBC",
            "description": "Complete Blood Count",
            "is_active": True,
        }]},
    )

    id: int
    name: str
    description: str
    is_active: bool


class CentreTestCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"price": 500.00}]})

    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class CentreTestRead(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "test": {
            "id": 2,
            "name": "CBC",
            "description": "Complete Blood Count",
            "is_active": True,
        },
        "price": 500.00,
    }]})

    test: TestRead
    price: Decimal
