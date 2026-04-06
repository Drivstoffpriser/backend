from typing import cast
from uuid import UUID

import sqlalchemy as sa

from app.core.db import DBSession
from app.favorite_stations.models import FavoriteStation


async def favorite_station_factory(
    db: DBSession,
    *,
    user_id: UUID,
    station_id: UUID,
) -> FavoriteStation:
    result = await db.execute(
        sa.insert(FavoriteStation)
        .values(
            {FavoriteStation.user_id: user_id, FavoriteStation.station_id: station_id}
        )
        .returning(FavoriteStation)
    )
    return cast(FavoriteStation, result.scalar_one())
