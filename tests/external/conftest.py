from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import DBSession, get_db_session
from app.main import app


@pytest.fixture
async def client(db: DBSession) -> AsyncGenerator[AsyncClient]:
    async def override_db() -> AsyncGenerator[DBSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()
