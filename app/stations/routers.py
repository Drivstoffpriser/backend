from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from geoalchemy2 import Geometry

from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel, LocationSchema
from app.stations.enums import ProviderType
from app.stations.models import Station

stations_router = APIRouter(prefix="/stations", tags=["stations"])


class StationSchema(CamelCaseModel):
    id: UUID
    osm_id: str
    name: str
    provider: ProviderType
    address: str
    city: str
    location: LocationSchema


class GetStationsResponseBody(CamelCaseModel):
    stations: list[StationSchema]

    @classmethod
    def from_models(cls, stations: list[Station]) -> GetStationsResponseBody:
        return cls(
            stations=[
                StationSchema(
                    id=station.id,
                    osm_id=station.osm_id,
                    name=station.name,
                    provider=station.provider,
                    address=station.address,
                    city=station.city,
                    location=LocationSchema.from_wkb(station.location),
                )
                for station in stations
            ]
        )


@stations_router.get("/")
async def get_stations(
    db: Annotated[DBSession, Depends(get_db_session)],
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
    return GetStationsResponseBody.from_models(stations)


@stations_router.get("/bbox")
async def get_stations_bbox(
    db: Annotated[DBSession, Depends(get_db_session)],
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
    return GetStationsResponseBody.from_models(stations)
