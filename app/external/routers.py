from datetime import datetime
from typing import Annotated

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query

from app.core.db import DBSession, get_db_session
from app.external.auth import get_api_token
from app.external.models import ApiToken
from app.external.schemas import ExternalGetStationsResponseBody
from app.stations import services as stations_services
from app.stations.models import PriceRegistration, Station

external_router = APIRouter(prefix="/external", tags=["external"])


@external_router.get("/prices")
async def get_updated_prices(
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[ApiToken, Depends(get_api_token)],
    updated_since: Annotated[datetime, Query(alias="updatedSince")],
) -> ExternalGetStationsResponseBody:
    station_ids_query = (
        sa.select(PriceRegistration.station_id)
        .where(
            PriceRegistration.registered_at >= updated_since,
            PriceRegistration.is_latest.is_(True),
        )
        .distinct()
    )

    stations = await db.fetch_all(
        sa.select(Station).where(Station.id.in_(station_ids_query))
    )
    prices_by_station = await stations_services.fetch_latest_prices(
        db, [s.id for s in stations]
    )
    return ExternalGetStationsResponseBody.from_models(stations, prices_by_station)
