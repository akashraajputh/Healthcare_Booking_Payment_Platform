from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.test import TestCreate, TestRead

router = APIRouter(prefix="/tests", tags=["diagnostic tests"])


@router.post("/", response_model=TestRead, status_code=status.HTTP_201_CREATED)
async def create_test(
    payload: TestCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> DiagnosticTest:
    test = DiagnosticTest(name=payload.name, description=payload.description)
    session.add(test)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A test with this name already exists") from None
    await session.refresh(test)
    return test


@router.get("/", response_model=list[TestRead])
async def list_tests(session: AsyncSession = Depends(get_db)) -> list[DiagnosticTest]:
    result = await session.scalars(
        select(DiagnosticTest).where(DiagnosticTest.is_active.is_(True)).order_by(DiagnosticTest.name)
    )
    return list(result.all())


@router.get("/{test_id}", response_model=TestRead)
async def get_test(test_id: int, session: AsyncSession = Depends(get_db)) -> DiagnosticTest:
    test = await session.scalar(select(DiagnosticTest).where(DiagnosticTest.id == test_id, DiagnosticTest.is_active.is_(True)))
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    return test
