"""Seed the database with station data from the tankvenn dataset."""

import asyncio
import json
import urllib.request

from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.logging import logger
from app.stations.enums import BRAND_TO_PROVIDER
from app.stations.models import Station

STATIONS_URL = (
    "https://drivstoffpriser.github.io/Drivstoffpriser-App/data/stations.json"
)


async def seed() -> None:
    with urllib.request.urlopen(STATIONS_URL) as response:
        data = json.loads(response.read())

    stations = data["stations"]
    engine = create_async_engine(get_settings().database_url)

    async with engine.begin() as conn:
        for s in stations:
            if s["brand"] in BRAND_TO_PROVIDER:
                await conn.execute(
                    insert(Station)
                    .values(
                        {
                            Station.external_id: s["id"],
                            Station.name: s["name"],
                            Station.provider: BRAND_TO_PROVIDER[s["brand"]],
                            Station.address: s["address"] or "",
                            Station.city: s["city"] or "",
                            Station.location: WKTElement(
                                f"POINT({s['longitude']} {s['latitude']})", srid=4326
                            ),
                        }
                    )
                    .on_conflict_do_nothing()
                )
            else:
                logger.warning(f"Skipping unknown brand: {s['brand']}")

    await engine.dispose()
    print(f"Seeded {len(stations)} stations.")


asyncio.run(seed())
