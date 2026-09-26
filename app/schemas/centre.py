from pydantic import BaseModel, ConfigDict, Field


class CentreCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "Apollo Diagnostics", "location": "Delhi"}]})

    name: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=240)


class CentreRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{"id": 1, "name": "Apollo Diagnostics", "location": "Delhi", "is_active": True}]},
    )

    id: int
    name: str
    location: str
    is_active: bool
