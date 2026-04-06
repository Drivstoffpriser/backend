from collections import defaultdict
from uuid import UUID

import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.models import PriceRegistration


async def fetch_latest_prices(
    db: DBSession, station_ids: list[UUID]
) -> dict[UUID, list[PriceRegistration]]:
    if not station_ids:
        return {}

    prices = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id.in_(station_ids),
            PriceRegistration.is_latest.is_(True),
        )
    )
    result: dict[UUID, list[PriceRegistration]] = defaultdict(list)
    for price in prices:
        result[price.station_id].append(price)

    return result
