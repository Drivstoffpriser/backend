from datetime import UTC, datetime
from decimal import Decimal
from types import EllipsisType
from typing import cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from geoalchemy2.shape import from_shape
from shapely.geometry import Point  # type: ignore[import-untyped]

from app.core.db import DBSession
from app.stations.enums import FuelType, ProviderType
from app.stations.models import PriceRegistration, Station
from tests.users.factories import verified_user_factory


async def station_factory(
    db: DBSession,
    *,
    external_id: str = "node/123456",
    name: str | EllipsisType = ...,
    provider: ProviderType = ProviderType.CIRCLE_K,
    address: str | EllipsisType = ...,
    city: str = "Oslo",
    lat: float = 59.911,
    lng: float = 10.752,
) -> Station:
    if name is ...:
        name = f"Station {external_id}"
    if address is ...:
        address = f"Street {external_id}"

    result = await db.execute(
        sa.insert(Station)
        .values(
            {
                Station.id: uuid4(),
                Station.external_id: external_id,
                Station.name: name,
                Station.provider: provider,
                Station.address: address,
                Station.city: city,
                Station.location: from_shape(Point(lng, lat), srid=4326),
            }
        )
        .returning(Station)
    )
    return cast(Station, result.scalar_one())


async def price_update_factory(
    db: DBSession,
    *,
    station_id: UUID,
    registered_by: UUID | EllipsisType = ...,
    fuel_type: FuelType = FuelType.DIESEL,
    price: Decimal = Decimal("20.00"),
    registered_at: datetime | EllipsisType = ...,
) -> PriceRegistration:

    if registered_by is ...:
        firebase_uid = str(uuid4())
        registered_by = (
            await verified_user_factory(
                db=db, firebase_uid=firebase_uid, email=f"{firebase_uid}@example.com"
            )
        ).id
    if registered_at is ...:
        registered_at = datetime.now(UTC)

    await db.execute(
        sa.update(PriceRegistration)
        .where(
            PriceRegistration.station_id == station_id,
            PriceRegistration.fuel_type == fuel_type,
            PriceRegistration.is_latest.is_(True),
        )
        .values({PriceRegistration.is_latest: False})
    )

    result = await db.execute(
        sa.insert(PriceRegistration)
        .values(
            {
                PriceRegistration.station_id: station_id,
                PriceRegistration.registered_by: registered_by,
                PriceRegistration.fuel_type: fuel_type,
                PriceRegistration.price: price,
                PriceRegistration.registered_at: registered_at,
                PriceRegistration.is_latest: True,
            }
        )
        .returning(PriceRegistration)
    )
    return cast(PriceRegistration, result.scalar_one())
