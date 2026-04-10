import importlib
import pkgutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import Executable

from app.core.config import get_settings

T = TypeVar("T")


class Base(DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=sa.text("gen_random_uuid()")
    )
    _inserted_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )


class DBSession:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_all(self, statement: Select[tuple[T]]) -> list[T]:
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def fetch_one(self, statement: Select[tuple[T]]) -> T:
        result = await self._session.execute(statement)
        row = result.scalars().first()
        if row is None:
            raise NoResultFound
        return row

    async def fetch_one_or_none(self, statement: Select[tuple[T]]) -> T | None:
        result = await self._session.execute(statement)
        return result.scalars().first()

    async def execute(self, statement: Executable) -> Any:
        return await self._session.execute(statement)

    async def commit(self) -> None:
        await self._session.commit()


class Database:
    def __init__(self) -> None:
        settings = get_settings()
        self._engine = create_async_engine(settings.database_url, echo=False)
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[DBSession]:
        async with self._session_factory() as session:
            yield DBSession(session)


db = Database()


async def get_db_session() -> AsyncGenerator[DBSession]:
    async with db.session() as session:
        yield session


def import_all_models() -> None:
    """Import every app/*/models.py so all models register with Base.metadata."""
    import app

    for _, modname, _ in pkgutil.walk_packages(
        path=app.__path__,
        prefix=app.__name__ + ".",
    ):
        if modname.endswith(".models"):
            importlib.import_module(modname)
