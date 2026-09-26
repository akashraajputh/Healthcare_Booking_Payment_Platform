import os
from collections.abc import AsyncIterator
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-characters")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app
from app.models import User, UserRole
from app.core.security import hash_password


@pytest_asyncio.fixture
async def test_session_factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    database_path = tmp_path / "test.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}", connect_args={"timeout": 10})
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def client(test_session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict[str, object]:
    credentials = {"email": "patient@example.com", "password": "StrongPassword123", "full_name": "Patient One"}
    signup_response = await client.post("/auth/signup", json=credentials)
    assert signup_response.status_code == 201
    login_response = await client.post("/auth/login", json={"email": credentials["email"], "password": credentials["password"]})
    assert login_response.status_code == 200
    return {"user": signup_response.json(), "token": login_response.json()["access_token"]}


@pytest_asyncio.fixture
async def admin_user(
    client: AsyncClient, test_session_factory: async_sessionmaker[AsyncSession]
) -> dict[str, object]:
    email = "admin@example.com"
    response = await client.post(
        "/auth/signup",
        json={"email": email, "password": "AdminPassword123", "full_name": "Admin User"},
    )
    assert response.status_code == 201
    async with test_session_factory() as session:
        user = await session.get(User, response.json()["id"])
        assert user is not None
        user.role = UserRole.ADMIN
        await session.commit()
    login_response = await client.post("/auth/login", json={"email": email, "password": "AdminPassword123"})
    assert login_response.status_code == 200
    return {"user": response.json(), "token": login_response.json()["access_token"]}


@pytest_asyncio.fixture
async def catalog(client: AsyncClient, admin_user: dict[str, object]) -> dict[str, int]:
    headers = {"Authorization": f"Bearer {admin_user['token']}"}
    centre_response = await client.post(
        "/centres/", json={"name": "EVE Central Lab", "location": "Delhi"}, headers=headers
    )
    assert centre_response.status_code == 201
    test_response = await client.post(
        "/tests/", json={"name": "CBC", "description": "Complete blood count"}, headers=headers
    )
    assert test_response.status_code == 201
    association_response = await client.post(
        f"/centres/{centre_response.json()['id']}/tests/{test_response.json()['id']}",
        json={"price": "500.00"},
        headers=headers,
    )
    assert association_response.status_code == 201
    return {"centre_id": centre_response.json()["id"], "test_id": test_response.json()["id"]}
