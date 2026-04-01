import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.db import (
    Base,
    DBSession,
    get_db_session,
    import_all_models,
)
from app.core.db import (
    db as database,
)
from app.main import app

import_all_models()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    async def _run(coro):
        engine = create_async_engine(get_settings().database_url)
        async with engine.begin() as conn:
            await conn.run_sync(coro)
        await engine.dispose()

    asyncio.run(_run(Base.metadata.drop_all))
    asyncio.run(_run(Base.metadata.create_all))
    yield
    asyncio.run(_run(Base.metadata.drop_all))


@pytest.fixture
async def db() -> DBSession:
    async with database._engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(
            conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield DBSession(session)
        await conn.rollback()


@pytest.fixture
async def client(db: DBSession) -> AsyncClient:
    async def override_db():
        yield db

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
