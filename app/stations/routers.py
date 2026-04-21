import datetime as dt
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, NamedTuple
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2 import Geography, Geometry
from geoalchemy2.shape import from_shape
from pydantic import Field, field_validator
from shapely.geometry import Point  # type: ignore[import-untyped]

from app.core.auth import get_admin_user, get_current_user, get_logged_in_user
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
)


class EstimatedPrice(NamedTuple):
    fuel_type: FuelType
    price: Decimal


class PriceSchema(CamelCaseModel):
    fuel_type: FuelType
    price: Decimal
    registered_at: datetime | None


class StationBaseSchema(CamelCaseModel):
    id: UUID
    external_id: str
    name: str
    provider: ProviderType
    address: str
    city: str
    location: LocationSchema


class StationSchema(StationBaseSchema):
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
                  AND ST_DWithin(sne.location, s2.location, 100000)
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


@stations_router.get("")
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

    user_point = sa.cast(
        sa.func.ST_SetSRID(sa.func.ST_MakePoint(lng, lat), 4326), Geography
    )
    base_query = sa.select(Station).where(
        sa.func.ST_DWithin(Station.location, user_point, distance)
    )

    match sort:
        case StationSortType.NEAREST:
            query = base_query.order_by(
                sa.func.ST_Distance(Station.location, user_point)
            )
        case StationSortType.CHEAPEST:
            query = (
                sa.select(Station)
                .join(
                    PriceRegistration,
                    PriceRegistration.station_id == Station.id,
                )
                .where(
                    sa.func.ST_DWithin(Station.location, user_point, distance),
                    PriceRegistration.is_latest.is_(True),
                    PriceRegistration.fuel_type == fuel_type,
                )
                .order_by(PriceRegistration.price.asc())
            )
        case StationSortType.LATEST:
            latest_q = sa.select(
                PriceRegistration.station_id,
                sa.func.max(PriceRegistration.registered_at).label("latest_at"),
            ).group_by(PriceRegistration.station_id)
            if fuel_type is not None:
                latest_q = latest_q.where(PriceRegistration.fuel_type == fuel_type)
            latest_subq = latest_q.subquery()
            query = base_query.outerjoin(
                latest_subq, Station.id == latest_subq.c.station_id
            ).order_by(sa.nulls_last(latest_subq.c.latest_at.desc()))
        case _:
            raise HTTPException(status_code=422, detail="Invalid sort type")

    stations = await db.fetch_all(query.limit(50))
    prices_by_station = await _fetch_latest_prices(db, [s.id for s in stations])
    return GetStationsResponseBody.from_models(stations, prices_by_station)


@stations_router.get("/bbox")
async def get_stations_bbox(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    min_lat: Annotated[float, Query(alias="minLat")],
    min_lng: Annotated[float, Query(alias="minLng")],
    max_lat: Annotated[float, Query(alias="maxLat")],
    max_lng: Annotated[float, Query(alias="maxLng")],
) -> GetStationsResponseBody:
    lat_padding = (max_lat - min_lat) / 2
    lng_padding = (max_lng - min_lng) / 2
    bbox = sa.func.ST_MakeEnvelope(
        min_lng - lng_padding,
        min_lat - lat_padding,
        max_lng + lng_padding,
        max_lat + lat_padding,
        4326,
    )
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


class SearchStationsResponseBody(CamelCaseModel):
    stations: list[StationBaseSchema]


@stations_router.get("/search")
async def search_stations(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    query: Annotated[str, Query(min_length=1)],
) -> SearchStationsResponseBody:
    stations = await db.fetch_all(
        sa.select(Station)
        .where(sa.func.similarity(Station.name, query) > 0.1)
        .order_by(sa.func.similarity(Station.name, query).desc())
        .limit(20)
    )
    return SearchStationsResponseBody(
        stations=[
            StationBaseSchema(
                id=s.id,
                external_id=s.external_id,
                name=s.name,
                provider=s.provider,
                address=s.address,
                city=s.city,
                location=LocationSchema.from_wkb(s.location),
            )
            for s in stations
        ]
    )


@stations_router.get("/all")
async def get_all_stations(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
) -> SearchStationsResponseBody:
    stations = await db.fetch_all(sa.select(Station))
    return SearchStationsResponseBody(
        stations=[
            StationBaseSchema(
                id=s.id,
                external_id=s.external_id,
                name=s.name,
                provider=s.provider,
                address=s.address,
                city=s.city,
                location=LocationSchema.from_wkb(s.location),
            )
            for s in stations
        ]
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


class LastUpdatedSchema(CamelCaseModel):
    last_updated_at: datetime | None


@stations_router.get("/last-updated")
async def get_last_updated(
    db: Annotated[DBSession, Depends(get_db_session)],
) -> LastUpdatedSchema:
    last_updated_at = await db.fetch_one_or_none(
        sa.select(sa.func.max(Station.updated_at))
    )
    return LastUpdatedSchema(last_updated_at=last_updated_at)


class StationPricesSchema(CamelCaseModel):
    station_id: UUID
    prices: list[PriceSchema] = []


class GetPricesByStationIdsResponseBody(CamelCaseModel):
    stations: list[StationPricesSchema]


@stations_router.get("/prices")
async def get_prices_by_station_ids(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
    station_ids: Annotated[list[UUID], Query(alias="stationIds")],
) -> GetPricesByStationIdsResponseBody:
    prices_by_station = await _fetch_latest_prices(db, station_ids)
    unpriced_ids = [sid for sid in station_ids if sid not in prices_by_station]
    estimates_by_station = await _fetch_estimated_prices(db, unpriced_ids)
    return GetPricesByStationIdsResponseBody(
        stations=[
            StationPricesSchema(
                station_id=sid,
                prices=[
                    PriceSchema(
                        fuel_type=p.fuel_type,
                        price=p.price,
                        registered_at=p.registered_at,
                    )
                    for p in prices_by_station.get(sid, [])
                ]
                + [
                    PriceSchema(
                        fuel_type=e.fuel_type,
                        price=e.price,
                        registered_at=None,
                    )
                    for e in estimates_by_station.get(sid, [])
                ],
            )
            for sid in station_ids
        ]
    )


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


class UpdateStationRequestBody(CamelCaseModel):
    name: str | None = None
    provider: ProviderType | None = None
    address: str | None = None
    city: str | None = None
    location: LocationSchema | None = None


@stations_router.patch("/{station_id}", status_code=200)
async def update_station(
    station_id: UUID,
    body: UpdateStationRequestBody,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_admin_user)],
) -> StationBaseSchema:
    station = await db.fetch_one_or_none(
        sa.select(Station).where(Station.id == station_id)
    )
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Station not found"
        )

    values: dict[sa.orm.InstrumentedAttribute[Any], Any] = {}
    if body.name is not None:
        values[Station.name] = body.name
    if body.provider is not None:
        values[Station.provider] = body.provider
    if body.address is not None:
        values[Station.address] = body.address
    if body.city is not None:
        values[Station.city] = body.city
    if body.location is not None:
        values[Station.location] = from_shape(
            Point(body.location.lng, body.location.lat), srid=4326
        )

    if not values:
        return StationBaseSchema(
            id=station.id,
            external_id=station.external_id,
            name=station.name,
            provider=station.provider,
            address=station.address,
            city=station.city,
            location=LocationSchema.from_wkb(station.location),
        )

    values[Station.updated_at] = sa.func.now()

    result = await db.execute(
        sa.update(Station)
        .where(Station.id == station_id)
        .values(values)
        .returning(Station)
    )
    updated = result.scalars().one()
    await db.commit()

    return StationBaseSchema(
        id=updated.id,
        external_id=updated.external_id,
        name=updated.name,
        provider=updated.provider,
        address=updated.address,
        city=updated.city,
        location=LocationSchema.from_wkb(updated.location),
    )


@stations_router.delete("/{station_id}", status_code=204)
async def delete_station(
    station_id: UUID,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_admin_user)],
) -> None:
    station = await db.fetch_one_or_none(
        sa.select(Station).where(Station.id == station_id)
    )
    if station is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Station not found"
        )

    await db.execute(sa.delete(Station).where(Station.id == station_id))
    await db.commit()


@stations_router.delete("/{station_id}/prices/{price_id}", status_code=204)
async def delete_price_registration(
    station_id: UUID,
    price_id: UUID,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_admin_user)],
) -> None:
    registration = await db.fetch_one_or_none(
        sa.select(PriceRegistration).where(
            PriceRegistration.id == price_id,
            PriceRegistration.station_id == station_id,
        )
    )
    if registration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price registration not found"
        )

    await db.execute(
        sa.delete(PriceRegistration).where(PriceRegistration.id == price_id)
    )

    if registration.is_latest:
        next_latest = await db.fetch_one_or_none(
            sa.select(PriceRegistration)
            .where(
                PriceRegistration.station_id == station_id,
                PriceRegistration.fuel_type == registration.fuel_type,
            )
            .order_by(PriceRegistration.registered_at.desc())
            .limit(1)
        )
        if next_latest is not None:
            await db.execute(
                sa.update(PriceRegistration)
                .where(PriceRegistration.id == next_latest.id)
                .values({PriceRegistration.is_latest: True})
            )

    await db.commit()
