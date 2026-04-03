"""Seed the database with station data from the tankvenn dataset."""

import asyncio
import json
import urllib.request

from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.stations.enums import ProviderType
from app.stations.models import Station

BRAND_TO_PROVIDER: dict[str, ProviderType] = {
    "Automat1": ProviderType.AUTOMAT_1,
    "Best": ProviderType.BEST,
    "Bunker Oil": ProviderType.BUNKER_OIL,
    "Circle K": ProviderType.CIRCLE_K,
    "Driv": ProviderType.DRIV,
    "Esso": ProviderType.ESSO,
    "Haltbakk Express": ProviderType.HALTBAKK_EXPRESS,
    "St1": ProviderType.ST1,
    "Tanken": ProviderType.TANKEN,
    "Uno-X": ProviderType.UNO_X,
    "YX": ProviderType.YX,
    "YX Truck": ProviderType.YX_TRUCK,
}

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
            await conn.execute(
                insert(Station)
                .values(
                    {
                        Station.osm_id: s["id"],
                        Station.name: s["name"],
                        Station.provider: BRAND_TO_PROVIDER[s["brand"]],
                        Station.address: s["address"] or "",
                        Station.city: s["city"] or "",
                        Station.location: WKTElement(
                            f"POINT({s['longitude']} {s['latitude']})", srid=4326
                        ),
                    }
                )
                .on_conflict_do_nothing(index_elements=[Station.osm_id])
            )

    await engine.dispose()
    print(f"Seeded {len(stations)} stations.")


asyncio.run(seed())
