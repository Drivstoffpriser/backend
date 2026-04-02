"""Drop all app tables and alembic tracking, leaving PostGIS system tables intact."""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.db import Base, import_all_models

import_all_models()

settings = get_settings()
if not settings.debug:
    print("ERROR: reset_db.py can only run with DEBUG=true")
    sys.exit(1)


async def reset() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()
    print("Database reset.")


asyncio.run(reset())
