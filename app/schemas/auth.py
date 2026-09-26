from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "email": "akash@example.com",
        "password": "StrongPassword123",
        "full_name": "Akash Kumar",
    }]})

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "email": "akash@example.com",
        "password": "StrongPassword123",
    }]})

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"examples": [{"id": 1, "email": "akash@example.com", "full_name": "Akash Kumar"}]},
    )

    id: int
    email: EmailStr
    full_name: str


class TokenResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "access_token": "<JWT returned by /auth/login>",
        "token_type": "bearer",
    }]})

    access_token: str
    token_type: str = "bearer"
