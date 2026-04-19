import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import sqlalchemy as sa
from apscheduler.schedulers.asyncio import (  # type: ignore[import-untyped]
    AsyncIOScheduler,
)
from apscheduler.triggers.interval import (  # type: ignore[import-untyped]
    IntervalTrigger,
)
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import DBSession, get_db_session
from app.core.logging import logger
from app.favorite_stations.routers import favorite_stations_router
from app.stations.routers import stations_router
from app.stations.sync import sync_prices_from_firestore
from app.tools.routers import tools_router
from app.users.routers import users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        sync_prices_from_firestore,
        IntervalTrigger(minutes=10),
        id="sync_prices",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title=get_settings().app_name,
    debug=get_settings().debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s %d %.0fms", request.method, request.url.path, response.status_code, ms
    )
    return response


app.include_router(favorite_stations_router)
app.include_router(stations_router)
app.include_router(users_router)
app.include_router(tools_router)


@app.get("/health", status_code=200)
async def health(
    db: Annotated[DBSession, Depends(get_db_session)],
) -> dict[str, str]:
    await db.execute(sa.text("SELECT 1"))
    return {"status": "ok"}
