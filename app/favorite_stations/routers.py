from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.auth import get_current_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel
from app.favorite_stations.models import FavoriteStation
from app.users.models import User

favorite_stations_router = APIRouter(prefix="/favorites", tags=["favorites"])


class FavoriteStationRequest(CamelCaseModel):
    station_id: UUID


@favorite_stations_router.get("")
async def get_favorite_stations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> list[UUID]:
    return await db.fetch_all(
        sa.select(FavoriteStation.station_id).where(
            FavoriteStation.user_id == current_user.id
        )
    )


@favorite_stations_router.post("", status_code=201)
async def add_favorite_station(
    body: FavoriteStationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    await db.execute(
        pg_insert(FavoriteStation)
        .values(
            {
                FavoriteStation.user_id: current_user.id,
                FavoriteStation.station_id: body.station_id,
            }
        )
        .on_conflict_do_nothing(constraint="uq_favorite_station_user_station")
    )


@favorite_stations_router.delete("", status_code=204)
async def remove_favorite_station(
    body: FavoriteStationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    result = await db.execute(
        sa.delete(FavoriteStation).where(
            FavoriteStation.user_id == current_user.id,
            FavoriteStation.station_id == body.station_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Favorite not found"
        )
