import datetime as dt
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, NamedTuple
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_limiter.depends import RateLimiter
from geoalchemy2 import Geometry
from pydantic import Field, field_validator
from pyrate_limiter import Duration, Limiter, Rate

from app.core.auth import get_current_user, get_logged_in_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel, LocationSchema
from app.stations.enums import FuelType, ProviderType
from app.stations.models import PriceRegistration, Station
from app.users.models import User


class StationSortType(StrEnum):
    NEAREST = "nearest"
    CHEAPEST = "cheapest"
    LATEST = "latest"


stations_router = APIRouter(
    prefix="/stations",
    tags=["stations"],
    dependencies=[
        Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 10))))
    ],
)


class EstimatedPrice(NamedTuple):
    fuel_type: FuelType
    price: Decimal


class PriceSchema(CamelCaseModel):
    fuel_type: FuelType
    price: Decimal
    registered_at: datetime | None


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
        estimates_by_station: dict[UUID, list[EstimatedPrice]] | None = None,
    ) -> GetStationsResponseBody:
        prices_by_station = prices_by_station or {}
        estimates_by_station = estimates_by_station or {}
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
                    ]
                    + [
                        PriceSchema(
                            fuel_type=e.fuel_type,
                            price=e.price,
                            registered_at=None,
                        )
                        for e in estimates_by_station.get(station.id, [])
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


async def _fetch_estimated_prices(
    db: DBSession, station_ids: list[UUID]
) -> dict[UUID, list[EstimatedPrice]]:
    """For each station without real prices, average the 5 nearest stations'
    prices per fuel type using a PostGIS LATERAL join."""
    if not station_ids:
        return {}

    result = await db.execute(
        sa.text("""
            SELECT
                sne.id       AS station_id,
                ft.fuel_type,
                ROUND(AVG(nearby.price), 2) AS price
            FROM station sne
            CROSS JOIN (VALUES ('DIESEL'), ('GASOLINE_95')) AS ft(fuel_type)
            CROSS JOIN LATERAL (
                SELECT pr.price
                FROM price_registration pr
                JOIN station s2 ON s2.id = pr.station_id
                WHERE pr.is_latest = true
                  AND pr.fuel_type = ft.fuel_type
                  AND s2.id != sne.id
                ORDER BY ST_Distance(sne.location, s2.location)
                LIMIT 5
            ) nearby
            WHERE sne.id = ANY(:station_ids)
            GROUP BY sne.id, ft.fuel_type
        """).bindparams(
            sa.bindparam("station_ids", value=station_ids, type_=sa.ARRAY(sa.Uuid))
        )
    )
    estimates: dict[UUID, list[EstimatedPrice]] = defaultdict(list)
    for row in result.all():
        estimates[row.station_id].append(
            EstimatedPrice(fuel_type=row.fuel_type, price=row.price)
        )
    return estimates


@stations_router.get("/")
async def get_stations(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    distance: Annotated[float, Query(gt=0, description="Max distance in meters")],
    sort: Annotated[StationSortType, Query()] = StationSortType.NEAREST,
    fuel_type: Annotated[FuelType | None, Query(alias="fuelType")] = None,
) -> GetStationsResponseBody:
    if sort == StationSortType.CHEAPEST and fuel_type is None:
        raise HTTPException(
            status_code=422, detail="fuelType is required when sort=cheapest"
        )

    user_point = sa.func.ST_GeogFromText(f"POINT({lng} {lat})")
    base_query = sa.select(Station).where(
        sa.func.ST_DWithin(Station.location, user_point, distance)
    )

    match sort:
        case StationSortType.NEAREST:
            query = base_query.order_by(
                sa.func.ST_Distance(Station.location, user_point)
            )
        case StationSortType.CHEAPEST:
            price_subq = (
                sa.select(PriceRegistration.station_id, PriceRegistration.price)
                .where(
                    PriceRegistration.is_latest.is_(True),
                    PriceRegistration.fuel_type == fuel_type,
                )
                .subquery()
            )
            query = base_query.outerjoin(
                price_subq, Station.id == price_subq.c.station_id
            ).order_by(sa.nulls_last(price_subq.c.price.asc()))
        case StationSortType.LATEST:
            latest_subq = (
                sa.select(
                    PriceRegistration.station_id,
                    sa.func.max(PriceRegistration.registered_at).label("latest_at"),
                )
                .group_by(PriceRegistration.station_id)
                .subquery()
            )
            query = base_query.outerjoin(
                latest_subq, Station.id == latest_subq.c.station_id
            ).order_by(sa.nulls_last(latest_subq.c.latest_at.desc()))
        case _:
            raise HTTPException(status_code=422, detail="Invalid sort type")

    stations = await db.fetch_all(query.limit(50))
    prices_by_station = await _fetch_latest_prices(db, [s.id for s in stations])
    unpriced_station_ids = [s.id for s in stations if s.id not in prices_by_station]
    estimates_by_station = await _fetch_estimated_prices(db, unpriced_station_ids)

    return GetStationsResponseBody.from_models(
        stations, prices_by_station, estimates_by_station
    )


@stations_router.get("/bbox")
async def get_stations_bbox(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    min_lat: Annotated[float, Query(alias="minLat")],
    min_lng: Annotated[float, Query(alias="minLng")],
    max_lat: Annotated[float, Query(alias="maxLat")],
    max_lng: Annotated[float, Query(alias="maxLng")],
) -> GetStationsResponseBody:
    bbox = sa.func.ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
    stations = await db.fetch_all(
        sa.select(Station).where(
            sa.func.ST_Within(sa.cast(Station.location, Geometry(srid=4326)), bbox)
        )
    )
    prices_by_station = await _fetch_latest_prices(db, [s.id for s in stations])
    unpriced_station_ids = [s.id for s in stations if s.id not in prices_by_station]
    estimates_by_station = await _fetch_estimated_prices(db, unpriced_station_ids)

    return GetStationsResponseBody.from_models(
        stations, prices_by_station, estimates_by_station
    )


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


class PriceHistoryDaySchema(CamelCaseModel):
    date: dt.date
    average_price: Decimal


class RecentUpdateSchema(CamelCaseModel):
    id: UUID
    fuel_type: FuelType
    price: Decimal
    registered_at: datetime


class GetPriceHistoryResponseBody(CamelCaseModel):
    history: dict[FuelType, list[PriceHistoryDaySchema]]
    recent_updates: list[RecentUpdateSchema]


@stations_router.get("/{station_id}/history")
async def get_price_history(
    station_id: UUID,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
) -> GetPriceHistoryResponseBody:
    date_col = sa.cast(PriceRegistration.registered_at, sa.Date).label("date")
    avg_col = sa.func.round(sa.func.avg(PriceRegistration.price), 2).label(
        "average_price"
    )
    history_result = await db.execute(
        sa.select(PriceRegistration.fuel_type, date_col, avg_col)
        .where(
            PriceRegistration.station_id == station_id,
            PriceRegistration.registered_at
            >= sa.func.now() - sa.text("interval '30 days'"),
        )
        .group_by(PriceRegistration.fuel_type, date_col)
        .order_by(PriceRegistration.fuel_type, date_col)
    )
    recent = await db.fetch_all(
        sa.select(PriceRegistration)
        .where(PriceRegistration.station_id == station_id)
        .order_by(PriceRegistration.registered_at.desc())
        .limit(10)
    )
    history: dict[FuelType, list[PriceHistoryDaySchema]] = {ft: [] for ft in FuelType}
    for row in history_result.all():
        history[row.fuel_type].append(
            PriceHistoryDaySchema(date=row.date, average_price=row.average_price)
        )

    return GetPriceHistoryResponseBody(
        history=history,
        recent_updates=[
            RecentUpdateSchema(
                id=r.id,
                fuel_type=r.fuel_type,
                price=r.price,
                registered_at=r.registered_at,
            )
            for r in recent
        ],
    )


@stations_router.post("/{station_id}/prices", status_code=201)
async def register_prices(
    station_id: UUID,
    body: RegisterPricesRequestBody,
    db: Annotated[DBSession, Depends(get_db_session)],
    logged_in_user: Annotated[User, Depends(get_logged_in_user)],
    _: Annotated[
        RateLimiter,
        Depends(RateLimiter(limiter=Limiter(Rate(1, Duration.SECOND * 30)))),
    ],
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
                    PriceRegistration.registered_by: logged_in_user.id,
                    PriceRegistration.is_latest: True,
                }
            )
        )
    await db.commit()
