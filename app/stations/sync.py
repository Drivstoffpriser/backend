"""Sync of station and price data from Firestore to PostgreSQL."""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa

from app.core.db import DBSession, db
from app.core.firestore import fetch_all_prices_sync
from app.core.logging import logger
from app.stations.enums import (
    FIRESTORE_FUEL_TYPE_MAP,
    FuelType,
    PriceRegistrationSourceType,
)
from app.stations.models import PriceRegistration, Station

PRICE_REQUIRED_FIELDS = ("stationId", "fuelType", "price")


async def sync_prices_from_firestore() -> None:
    """Scheduler entry point: opens its own session and delegates to _sync_prices."""
    async with db.session() as session:
        await _sync_prices(session)


async def _sync_prices(session: DBSession) -> None:  # noqa: C901
    """Fetch currentPrices from Firestore and update PostgreSQL.

    Accepts a DBSession so it can be called directly in tests.
    Swallows all exceptions so a Firestore outage does not crash the scheduler.
    """
    try:
        raw_prices = await asyncio.to_thread(fetch_all_prices_sync)
        logger.info("Fetched %d price docs from Firestore", len(raw_prices))

        stations = await session.fetch_all(sa.select(Station))
        station_id_by_external_id: dict[str, UUID] = {
            s.external_id: s.id for s in stations
        }

        latest_prices = await session.fetch_all(
            sa.select(PriceRegistration).where(PriceRegistration.is_latest.is_(True))
        )
        current_prices: dict[tuple[UUID, FuelType], tuple[Decimal, datetime]] = {
            (r.station_id, r.fuel_type): (r.price, r.registered_at)
            for r in latest_prices
        }

        updated = 0
        skipped = 0

        for doc in raw_prices:
            if missing := [f for f in PRICE_REQUIRED_FIELDS if f not in doc]:
                logger.warning("Skipping price doc with missing fields %s", missing)
                skipped += 1
                continue

            station_id = station_id_by_external_id.get(str(doc["stationId"]))
            if station_id is None:
                skipped += 1
                continue

            fuel_type = FIRESTORE_FUEL_TYPE_MAP.get(str(doc["fuelType"]))
            if fuel_type is None:
                skipped += 1
                continue

            incoming_price = Decimal(str(doc["price"])).quantize(Decimal("0.01"))

            raw_updated_at = doc.get("updatedAt")
            if raw_updated_at is not None:
                dt = datetime.fromisoformat(str(raw_updated_at))
                registered_at = (
                    dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
                )
            else:
                registered_at = datetime.now(UTC)

            current = current_prices.get((station_id, fuel_type))
            is_latest = current is None or registered_at > current[1]

            if is_latest:
                await session.execute(
                    sa.update(PriceRegistration)
                    .where(
                        PriceRegistration.station_id == station_id,
                        PriceRegistration.fuel_type == fuel_type,
                        PriceRegistration.is_latest.is_(True),
                    )
                    .values({PriceRegistration.is_latest: False})
                )

            await session.execute(
                sa.insert(PriceRegistration).values(
                    {
                        PriceRegistration.station_id: station_id,
                        PriceRegistration.fuel_type: fuel_type,
                        PriceRegistration.price: incoming_price,
                        PriceRegistration.source_type: (
                            PriceRegistrationSourceType.FIRESTORE
                        ),
                        PriceRegistration.registered_by: None,
                        PriceRegistration.registered_at: registered_at,
                        PriceRegistration.is_latest: is_latest,
                    }
                )
            )
            if is_latest:
                current_prices[(station_id, fuel_type)] = (
                    incoming_price,
                    registered_at,
                )
            updated += 1

        await session.commit()
        logger.info(
            "Firestore price sync complete: %d updated, %d skipped",
            updated,
            skipped,
        )
    except Exception:
        logger.exception("Firestore price sync failed")
