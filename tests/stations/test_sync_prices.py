from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import sqlalchemy as sa

from app.core.db import DBSession
from app.core.firestore import fetch_all_prices_sync
from app.stations import sync as sync_module
from app.stations.enums import FuelType, PriceRegistrationSourceType
from app.stations.models import PriceRegistration
from app.stations.sync import _sync_prices
from tests.stations.factories import price_update_factory, station_factory

OLDER = "2026-01-01T10:00:00"
NEWER = "2026-06-01T10:00:00"


async def test_inserts_price_when_none_exists(db: DBSession) -> None:
    station = await station_factory(db, external_id="osm_111")

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_111",
                "fuelType": "petrol95",
                "price": 21.08,
                "updatedAt": NEWER,
            }
        ],
    ):
        await _sync_prices(db)

    row = await db.fetch_one(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.GASOLINE_95,
            PriceRegistration.is_latest.is_(True),
        )
    )
    assert row.price == Decimal("21.08")
    assert row.source_type == PriceRegistrationSourceType.FIRESTORE
    assert row.registered_by is None


async def test_updates_price_when_different(db: DBSession) -> None:
    station = await station_factory(db, external_id="osm_222")
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("19.00")
    )

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_222",
                "fuelType": "diesel",
                "price": 20.50,
                "updatedAt": NEWER,
            }
        ],
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.DIESEL,
        )
    )
    latest = [r for r in rows if r.is_latest]
    old = [r for r in rows if not r.is_latest]
    assert len(latest) == 1
    assert latest[0].price == Decimal("20.50")
    assert latest[0].source_type == PriceRegistrationSourceType.FIRESTORE
    assert len(old) == 1
    assert old[0].price == Decimal("19.00")


async def test_inserts_when_same_price_but_newer(db: DBSession) -> None:
    station = await station_factory(db, external_id="osm_333")
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("21.08"),
        registered_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_333",
                "fuelType": "petrol95",
                "price": 21.08,
                "updatedAt": NEWER,
            }
        ],
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.GASOLINE_95,
        )
    )
    assert len(rows) == 2
    latest = next(r for r in rows if r.is_latest)
    assert latest.source_type == PriceRegistrationSourceType.FIRESTORE


async def test_skips_when_same_price_and_not_newer(db: DBSession) -> None:
    station = await station_factory(db, external_id="osm_444")
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_444",
                "fuelType": "diesel",
                "price": 20.00,
                "updatedAt": OLDER,
            }
        ],
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
        )
    )
    assert len(rows) == 1


async def test_skips_unknown_station(db: DBSession) -> None:
    await station_factory(db, external_id="osm_555")

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_UNKNOWN",
                "fuelType": "diesel",
                "price": 20.00,
                "updatedAt": NEWER,
            }
        ],
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(sa.select(PriceRegistration))
    assert len(rows) == 0


async def test_skips_unknown_fuel_type(db: DBSession) -> None:
    station = await station_factory(db, external_id="osm_666")

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[
            {
                "stationId": "osm_666",
                "fuelType": "hydrogen",
                "price": 20.00,
                "updatedAt": NEWER,
            }
        ],
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
        )
    )
    assert len(rows) == 0


async def test_skips_doc_with_missing_fields(db: DBSession) -> None:
    await station_factory(db, external_id="osm_777")

    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        return_value=[{"stationId": "osm_777", "fuelType": "diesel"}],  # missing price
    ):
        await _sync_prices(db)

    rows = await db.fetch_all(sa.select(PriceRegistration))
    assert len(rows) == 0


async def test_does_not_crash_on_firestore_exception(db: DBSession) -> None:
    with patch.object(
        sync_module,
        fetch_all_prices_sync.__name__,
        side_effect=Exception("Firestore unavailable"),
    ):
        await _sync_prices(db)  # must not raise
