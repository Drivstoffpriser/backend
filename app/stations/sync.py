"""Nightly sync of station data from Firestore to PostgreSQL."""

import asyncio

from geoalchemy2.elements import WKTElement
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.core.db import db
from app.core.firestore import fetch_all_stations_sync
from app.core.logging import logger
from app.stations.enums import BRAND_TO_PROVIDER
from app.stations.models import Station

REQUIRED_FIELDS = ("id", "name", "longitude", "latitude")


async def sync_stations_from_firestore() -> None:
    """Fetch all stations from Firestore and upsert into PostgreSQL."""
    try:
        raw_stations = await asyncio.to_thread(fetch_all_stations_sync)
        logger.info("Fetched %d stations from Firestore", len(raw_stations))

        synced = 0
        skipped = 0

        async with db._engine.begin() as conn:
            for doc in raw_stations:
                if missing := [f for f in REQUIRED_FIELDS if f not in doc]:
                    logger.warning(
                        "Skipping station with missing fields %s: %s",
                        missing,
                        doc.get("id", "<no id>"),
                    )
                    skipped += 1
                    continue

                brand = doc.get("brand", "")
                provider = BRAND_TO_PROVIDER.get(str(brand))
                if provider is None:
                    skipped += 1
                    continue

                values = {
                    "external_id": doc["id"],
                    "name": doc["name"],
                    "provider": provider,
                    "address": doc.get("address") or "",
                    "city": doc.get("city") or "",
                    "location": WKTElement(
                        f"POINT({doc['longitude']} {doc['latitude']})",
                        srid=4326,
                    ),
                }

                stmt = pg_insert(Station).values(values)
                savepoint = await conn.begin_nested()
                try:
                    await conn.execute(
                        stmt.on_conflict_do_update(
                            index_elements=[Station.external_id],
                            set_={
                                "name": stmt.excluded.name,
                                "provider": stmt.excluded.provider,
                                "address": stmt.excluded.address,
                                "city": stmt.excluded.city,
                                "location": stmt.excluded.location,
                            },
                        )
                    )
                    await savepoint.commit()
                    synced += 1
                except IntegrityError:
                    await savepoint.rollback()
                    logger.warning(
                        "Skipping station due to integrity error: %s (%s, %s, %s)",
                        doc.get("id"),
                        doc.get("name"),
                        doc.get("address"),
                        doc.get("city"),
                    )
                    skipped += 1

        logger.info(
            "Firestore station sync complete: %d synced, %d skipped",
            synced,
            skipped,
        )

    except Exception:
        logger.exception("Firestore station sync failed")
