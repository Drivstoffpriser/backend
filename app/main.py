from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.db import DBSession, get_db_session
from app.external.routers import external_router
from app.stations.routers import stations_router
from app.users.routers import users_router

app = FastAPI(title=get_settings().app_name, debug=get_settings().debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(external_router)
app.include_router(stations_router)
app.include_router(users_router)


@app.get("/health", status_code=200)
async def health(
    db: Annotated[DBSession, Depends(get_db_session)],
) -> dict[str, str]:
    await db.execute(sa.text("SELECT 1"))
    return {"status": "ok"}
