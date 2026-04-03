from uuid import uuid4

import sqlalchemy as sa
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.core.db import DBSession
from app.stations.enums import ProviderType
from app.stations.models import Station


async def station_factory(
    db: DBSession,
    *,
    osm_id: str = "node/123456",
    name: str = "Circle K Majorstuen",
    provider: ProviderType = ProviderType.CIRCLE_K,
    address: str = "Bogstadveien 1",
    city: str = "Oslo",
    lat: float = 59.911,
    lng: float = 10.752,
) -> Station:
    result = await db.execute(
        sa.insert(Station)
        .values(
            {
                Station.id: uuid4(),
                Station.osm_id: osm_id,
                Station.name: name,
                Station.provider: provider,
                Station.address: address,
                Station.city: city,
                Station.location: from_shape(Point(lng, lat), srid=4326),
            }
        )
        .returning(Station)
    )
    return result.scalar_one()
