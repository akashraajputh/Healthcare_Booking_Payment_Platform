from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models.centre import Centre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.models.user import User
from app.schemas.centre import CentreCreate, CentreRead
from app.schemas.test import CentreTestCreate, CentreTestRead

router = APIRouter(prefix="/centres", tags=["diagnostic centres"])


@router.post("/", response_model=CentreRead, status_code=status.HTTP_201_CREATED)
async def create_centre(
    payload: CentreCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Centre:
    centre = Centre(name=payload.name, location=payload.location)
    session.add(centre)
    await session.commit()
    await session.refresh(centre)
    return centre


@router.get("/", response_model=list[CentreRead])
async def list_centres(session: AsyncSession = Depends(get_db)) -> list[Centre]:
    result = await session.scalars(select(Centre).where(Centre.is_active.is_(True)).order_by(Centre.name))
    return list(result.all())


@router.get("/{centre_id}", response_model=CentreRead)
async def get_centre(centre_id: int, session: AsyncSession = Depends(get_db)) -> Centre:
    centre = await session.scalar(select(Centre).where(Centre.id == centre_id, Centre.is_active.is_(True)))
    if centre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")
    return centre


@router.post("/{centre_id}/tests/{test_id}", response_model=CentreTestRead, status_code=status.HTTP_201_CREATED)
async def associate_test(
    centre_id: int,
    test_id: int,
    payload: CentreTestCreate,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> CentreTestRead:
    centre = await session.scalar(select(Centre).where(Centre.id == centre_id))
    test = await session.scalar(select(DiagnosticTest).where(DiagnosticTest.id == test_id))
    if centre is None or test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre or test not found")
    association = await session.get(CentreTest, (centre_id, test_id))
    if association is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Test is already associated with this centre")
    association = CentreTest(centre_id=centre_id, test_id=test_id, price=payload.price)
    session.add(association)
    await session.commit()
    return CentreTestRead(test=test, price=association.price)


@router.get("/{centre_id}/tests", response_model=list[CentreTestRead])
async def list_centre_tests(centre_id: int, session: AsyncSession = Depends(get_db)) -> list[CentreTestRead]:
    centre = await session.scalar(select(Centre).where(Centre.id == centre_id, Centre.is_active.is_(True)))
    if centre is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Centre not found")
    result = await session.scalars(
        select(CentreTest)
        .options(joinedload(CentreTest.test))
        .where(CentreTest.centre_id == centre_id, DiagnosticTest.is_active.is_(True))
        .join(DiagnosticTest, CentreTest.test_id == DiagnosticTest.id)
        .order_by(DiagnosticTest.name)
    )
    return [CentreTestRead(test=item.test, price=item.price) for item in result.unique().all()]
