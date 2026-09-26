import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

logger = logging.getLogger(__name__)


async def signup(session: AsyncSession, email: str, password: str, full_name: str) -> User:
    normalized_email = email.lower()
    existing = await session.scalar(select(User.id).where(User.email == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(email=normalized_email, password_hash=hash_password(password), full_name=full_name)
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from None
    await session.refresh(user)
    logger.info("user_signup", extra={"user_id": user.id})
    return user


async def login(session: AsyncSession, email: str, password: str) -> str:
    normalized_email = email.lower()
    user = await session.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        logger.warning("login_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return create_access_token(user.id)
