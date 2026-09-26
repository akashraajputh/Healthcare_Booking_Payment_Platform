from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserRead
from app.services.auth_service import login, signup

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup_endpoint(payload: SignupRequest, session: AsyncSession = Depends(get_db)) -> UserRead:
    return await signup(session, payload.email, payload.password, payload.full_name)


@router.post("/login", response_model=TokenResponse)
async def login_endpoint(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    return TokenResponse(access_token=await login(session, payload.email, payload.password))
