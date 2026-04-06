from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geometry
from pydantic import Field, field_validator

from app.core.auth import get_current_user, get_verified_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel, LocationSchema
from app.stations.enums import FuelType, ProviderType
from app.stations.models import PriceRegistration, Station
from app.users.models import User

stations_router = APIRouter(prefix="/stations", tags=["stations"])


class PriceSchema(CamelCaseModel):
    fuel_type: FuelType
    price: Decimal
    registered_at: datetime


class StationSchema(CamelCaseModel):
    id: UUID
    external_id: str
    name: str
    provider: ProviderType
    address: str
    city: str
    location: LocationSchema
    prices: list[PriceSchema] = []


class GetStationsResponseBody(CamelCaseModel):
    stations: list[StationSchema]

    @classmethod
    def from_models(
        cls,
        stations: list[Station],
        prices_by_station: dict[UUID, list[PriceRegistration]] | None = None,
    ) -> GetStationsResponseBody:
        prices_by_station = prices_by_station or {}
        return cls(
            stations=[
                StationSchema(
                    id=station.id,
                    external_id=station.external_id,
                    name=station.name,
                    provider=station.provider,
                    address=station.address,
                    city=station.city,
                    location=LocationSchema.from_wkb(station.location),
                    prices=[
                        PriceSchema(
                            fuel_type=p.fuel_type,
                            price=p.price,
                            registered_at=p.registered_at,
                        )
                        for p in prices_by_station.get(station.id, [])
                    ],
                )
                for station in stations
            ]
        )


async def _fetch_latest_prices(
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


@stations_router.get("/")
async def get_stations(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    distance: Annotated[float, Query(gt=0, description="Max distance in meters")],
) -> GetStationsResponseBody:
    user_point = sa.func.ST_GeogFromText(f"POINT({lng} {lat})")
    stations = await db.fetch_all(
        sa.select(Station)
        .where(sa.func.ST_DWithin(Station.location, user_point, distance))
        .order_by(sa.func.ST_Distance(Station.location, user_point))
    )
    prices_by_station = await _fetch_latest_prices(db, [s.id for s in stations])
    return GetStationsResponseBody.from_models(stations, prices_by_station)


@stations_router.get("/bbox")
async def get_stations_bbox(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    min_lat: Annotated[float, Query()],
    min_lng: Annotated[float, Query()],
    max_lat: Annotated[float, Query()],
    max_lng: Annotated[float, Query()],
) -> GetStationsResponseBody:
    bbox = sa.func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
    stations = await db.fetch_all(
        sa.select(Station).where(
            sa.func.ST_Within(sa.cast(Station.location, Geometry(srid=4326)), bbox)
        )
    )
    prices_by_station = await _fetch_latest_prices(db, [s.id for s in stations])
    return GetStationsResponseBody.from_models(stations, prices_by_station)


PRICE_MIN = Decimal("10")
PRICE_MAX = Decimal("40")


class PriceRegistrationSchema(CamelCaseModel):
    fuel_type: FuelType
    price: Annotated[Decimal, Field(ge=PRICE_MIN, le=PRICE_MAX)]


class RegisterPricesRequestBody(CamelCaseModel):
    registrations: list[PriceRegistrationSchema]

    @field_validator("registrations")
    @classmethod
    def validate_no_duplicate_fuel_types(
        cls, v: list[PriceRegistrationSchema]
    ) -> list[PriceRegistrationSchema]:
        fuel_types = [r.fuel_type for r in v]
        if len(fuel_types) != len(set(fuel_types)):
            raise ValueError("Duplicate fuel types are not allowed")
        return v


@stations_router.post("/{station_id}/prices", status_code=201)
async def register_prices(
    station_id: UUID,
    body: RegisterPricesRequestBody,
    db: Annotated[DBSession, Depends(get_db_session)],
    verified_user: Annotated[User, Depends(get_verified_user)],
) -> None:
    fuel_types = [r.fuel_type for r in body.registrations]
    await db.execute(
        sa.update(PriceRegistration)
        .where(
            PriceRegistration.station_id == station_id,
            PriceRegistration.fuel_type.in_(fuel_types),
            PriceRegistration.is_latest.is_(True),
        )
        .values({PriceRegistration.is_latest: False})
    )
    for registration in body.registrations:
        await db.execute(
            sa.insert(PriceRegistration).values(
                {
                    PriceRegistration.station_id: station_id,
                    PriceRegistration.fuel_type: registration.fuel_type,
                    PriceRegistration.price: registration.price,
                    PriceRegistration.registered_by: verified_user.id,
                    PriceRegistration.is_latest: True,
                }
            )
        )
    await db.commit()
