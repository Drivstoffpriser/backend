from datetime import date as date_type
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geography
from pydantic import Field

from app.core.auth import get_current_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel
from app.stations.enums import FuelType, ProviderType
from app.stations.models import PriceRegistration, Station
from app.users.models import User

statistics_router = APIRouter(
    prefix="/statistics",
    tags=["statistics"],
)


class PriceStats(CamelCaseModel):
    highest_price: Decimal | None = None
    highest_station_id: UUID | None = None
    highest_station_name: str | None = None
    lowest_price: Decimal | None = None
    lowest_station_id: UUID | None = None
    lowest_station_name: str | None = None


class ActivityStats(CamelCaseModel):
    last_24_hours: int
    last_7_days: int
    last_30_days: int


class GetLatestStatisticsResponseBody(CamelCaseModel):
    all_stations: dict[FuelType, PriceStats]
    activity: ActivityStats


class GetNearestStatisticsResponseBody(CamelCaseModel):
    nearby_stations: dict[FuelType, PriceStats]


def _count_since(interval: sa.TextClause) -> sa.FunctionFilter[int]:
    return sa.func.count().filter(
        PriceRegistration.registered_at >= sa.func.now() - interval
    )


async def _fetch_price_stats(
    db: DBSession,
    where: sa.ColumnElement[bool] | None = None,
) -> dict[FuelType, PriceStats]:
    def _subquery(order: sa.UnaryExpression[Decimal], alias: str) -> sa.Subquery:
        q = (
            sa.select(
                PriceRegistration.fuel_type,
                PriceRegistration.price,
                Station.id.label("station_id"),
                Station.name.label("station_name"),
            )
            .join(Station, Station.id == PriceRegistration.station_id)
            .where(PriceRegistration.is_latest.is_(True))
            .distinct(PriceRegistration.fuel_type)
            .order_by(PriceRegistration.fuel_type, order)
        )
        if where is not None:
            q = q.where(where)
        return q.subquery(alias)

    high = _subquery(PriceRegistration.price.desc(), "high")
    low = _subquery(PriceRegistration.price.asc(), "low")

    result = await db.execute(
        sa.select(
            high.c.fuel_type,
            high.c.price.label("highest_price"),
            high.c.station_id.label("highest_station_id"),
            high.c.station_name.label("highest_station_name"),
            low.c.price.label("lowest_price"),
            low.c.station_id.label("lowest_station_id"),
            low.c.station_name.label("lowest_station_name"),
        ).join(low, high.c.fuel_type == low.c.fuel_type)
    )
    return {
        FuelType(row.fuel_type): PriceStats(
            highest_price=row.highest_price,
            highest_station_id=row.highest_station_id,
            highest_station_name=row.highest_station_name,
            lowest_price=row.lowest_price,
            lowest_station_id=row.lowest_station_id,
            lowest_station_name=row.lowest_station_name,
        )
        for row in result.all()
    }


@statistics_router.get("/latest")
async def get_latest_statistics(
    db: Annotated[DBSession, Depends(get_db_session)],
) -> GetLatestStatisticsResponseBody:
    all_stations = await _fetch_price_stats(db)

    _30_days = sa.text("interval '30 days'")
    activity_result = await db.execute(
        sa.select(
            _count_since(sa.text("interval '1 day'")).label("last_24_hours"),
            _count_since(sa.text("interval '7 days'")).label("last_7_days"),
            _count_since(_30_days).label("last_30_days"),
        ).where(PriceRegistration.registered_at >= sa.func.now() - _30_days)
    )
    row = activity_result.one()
    activity = ActivityStats(
        last_24_hours=row.last_24_hours,
        last_7_days=row.last_7_days,
        last_30_days=row.last_30_days,
    )

    return GetLatestStatisticsResponseBody(all_stations=all_stations, activity=activity)


@statistics_router.get("/nearest")
async def get_nearest_statistics(
    db: Annotated[DBSession, Depends(get_db_session)],
    lat: Annotated[float, Query()],
    lng: Annotated[float, Query()],
    distance: Annotated[float, Query(gt=0)] = 10_000,
) -> GetNearestStatisticsResponseBody:
    user_point = sa.cast(
        sa.func.ST_SetSRID(sa.func.ST_MakePoint(lng, lat), 4326), Geography
    )
    nearby_stations = await _fetch_price_stats(
        db,
        where=sa.func.ST_DWithin(Station.location, user_point, distance),
    )
    return GetNearestStatisticsResponseBody(nearby_stations=nearby_stations)


class ContributorSchema(CamelCaseModel):
    display_name: str | None
    count: int


class GetContributorsResponseBody(CamelCaseModel):
    last_24_hours: list[ContributorSchema]
    total: list[ContributorSchema]


async def _fetch_top_contributors(
    db: DBSession,
    where: sa.ColumnElement[bool] | None = None,
) -> list[ContributorSchema]:
    q = (
        sa.select(User.display_name, sa.func.count().label("count"))
        .select_from(PriceRegistration)
        .join(User, User.id == PriceRegistration.registered_by)
        .group_by(User.id)
        .order_by(sa.desc("count"))
        .limit(10)
    )
    if where is not None:
        q = q.where(where)
    result = await db.execute(q)
    return [
        ContributorSchema(display_name=row.display_name, count=row.count)
        for row in result.all()
    ]


@statistics_router.get("/contributors")
async def get_contributors(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_current_user)],
) -> GetContributorsResponseBody:
    last_24h_filter = PriceRegistration.registered_at >= sa.func.now() - sa.text(
        "interval '1 day'"
    )
    return GetContributorsResponseBody(
        last_24_hours=await _fetch_top_contributors(db, where=last_24h_filter),
        total=await _fetch_top_contributors(db),
    )


class ProviderPriceDaySchema(CamelCaseModel):
    date: date_type
    average_price: Decimal


ProviderPricesData = dict[ProviderType, dict[FuelType, list[ProviderPriceDaySchema]]]
ProviderPrices24hData = dict[ProviderType, dict[FuelType, Decimal]]


class GetProviderPricesResponseBody(CamelCaseModel):
    last_30d: ProviderPricesData = Field(alias="last30d", serialization_alias="last30d")
    last_24h: ProviderPrices24hData = Field(
        alias="last24h", serialization_alias="last24h"
    )


async def _fetch_provider_prices(db: DBSession, interval: str) -> ProviderPricesData:
    date_col = sa.cast(PriceRegistration.registered_at, sa.Date).label("date")
    avg_col = sa.func.round(sa.func.avg(PriceRegistration.price), 2).label(
        "average_price"
    )
    result = await db.execute(
        sa.select(Station.provider, PriceRegistration.fuel_type, date_col, avg_col)
        .join(Station, Station.id == PriceRegistration.station_id)
        .where(
            PriceRegistration.registered_at
            >= sa.func.now() - sa.text(f"interval '{interval}'")
        )
        .group_by(Station.provider, PriceRegistration.fuel_type, date_col)
        .order_by(Station.provider, PriceRegistration.fuel_type, date_col)
    )
    data: ProviderPricesData = {}
    for row in result.all():
        provider = ProviderType(row.provider)
        fuel = FuelType(row.fuel_type)
        data.setdefault(provider, {}).setdefault(fuel, []).append(
            ProviderPriceDaySchema(date=row.date, average_price=row.average_price)
        )
    return data


async def _fetch_provider_prices_24h(db: DBSession) -> ProviderPrices24hData:
    avg_col = sa.func.round(sa.func.avg(PriceRegistration.price), 2).label(
        "average_price"
    )
    result = await db.execute(
        sa.select(Station.provider, PriceRegistration.fuel_type, avg_col)
        .join(Station, Station.id == PriceRegistration.station_id)
        .where(
            PriceRegistration.registered_at
            >= sa.func.now() - sa.text("interval '1 day'")
        )
        .group_by(Station.provider, PriceRegistration.fuel_type)
        .order_by(Station.provider, PriceRegistration.fuel_type)
    )
    data: ProviderPrices24hData = {}
    for row in result.all():
        provider = ProviderType(row.provider)
        fuel = FuelType(row.fuel_type)
        data.setdefault(provider, {})[fuel] = row.average_price
    return data


@statistics_router.get("/provider-prices")
async def get_provider_prices(
    db: Annotated[DBSession, Depends(get_db_session)],
) -> GetProviderPricesResponseBody:
    last_30d = await _fetch_provider_prices(db, "30 days")
    last_24h = await _fetch_provider_prices_24h(db)
    return GetProviderPricesResponseBody(last_30d=last_30d, last_24h=last_24h)
