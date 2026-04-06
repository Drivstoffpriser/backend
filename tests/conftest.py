import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.core.db import (
    Base,
    DBSession,
    get_db_session,
    import_all_models,
)
from app.main import app
from app.users.models import User
from tests.users.factories import user_factory, verified_user_factory

import_all_models()


class AuthenticatedClient(AsyncClient):
    async def _request_with_auth(
        self, method: str, url: Any, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        if authenticate_with is not None:
            app.dependency_overrides[get_current_user] = lambda u=authenticate_with: u
        try:
            return await self.request(method, url, **kwargs)
        finally:
            if authenticate_with is not None:
                app.dependency_overrides.pop(get_current_user, None)

    async def get(
        self, url: Any, *, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        return await self._request_with_auth(
            "GET", url, authenticate_with=authenticate_with, **kwargs
        )

    async def post(
        self, url: Any, *, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        return await self._request_with_auth(
            "POST", url, authenticate_with=authenticate_with, **kwargs
        )

    async def put(
        self, url: Any, *, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        return await self._request_with_auth(
            "PUT", url, authenticate_with=authenticate_with, **kwargs
        )

    async def patch(
        self, url: Any, *, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        return await self._request_with_auth(
            "PATCH", url, authenticate_with=authenticate_with, **kwargs
        )

    async def delete(
        self, url: Any, *, authenticate_with: Any = None, **kwargs: Any
    ) -> Response:
        return await self._request_with_auth(
            "DELETE", url, authenticate_with=authenticate_with, **kwargs
        )


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None]:
    async def _run(coro: Callable[..., None]) -> None:
        engine = create_async_engine(get_settings().database_url)
        async with engine.begin() as conn:
            await conn.run_sync(coro)
        await engine.dispose()

    asyncio.run(_run(Base.metadata.drop_all))
    asyncio.run(_run(Base.metadata.create_all))
    yield
    asyncio.run(_run(Base.metadata.drop_all))


@pytest.fixture
async def db() -> AsyncGenerator[DBSession]:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(
            conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield DBSession(session)
        await conn.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db: DBSession) -> AsyncGenerator[AuthenticatedClient]:
    async def override_db() -> AsyncGenerator[DBSession]:
        yield db

    app.dependency_overrides[get_db_session] = override_db
    async with AuthenticatedClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def verified_user(db: DBSession) -> User:
    return await verified_user_factory(db=db)


@pytest.fixture
async def logged_in_user(db: DBSession) -> User:
    return await user_factory(
        db=db, email="loggedin@example.com", firebase_uid="logged-in-uid"
    )


@pytest.fixture
async def unverified_user(db: DBSession) -> User:
    return await user_factory(db=db)
