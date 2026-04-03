from decimal import Decimal

import sqlalchemy as sa
from httpx import AsyncClient

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.stations.models import PriceRegistration
from tests.stations.factories import price_update_factory, station_factory


async def test_register_prices_creates_records(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={
            "registrations": [
                {"fuelType": FuelType.DIESEL, "price": "20.00"},
                {"fuelType": FuelType.GASOLINE_95, "price": "22.90"},
            ]
        },
    )

    assert response.status_code == 201

    rows = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.is_latest.is_(True),
        )
    )
    by_fuel = {r.fuel_type: r for r in rows}
    assert by_fuel[FuelType.DIESEL].price == Decimal("20.00")
    assert by_fuel[FuelType.GASOLINE_95].price == Decimal("22.90")


async def test_register_prices_only_unsets_same_fuel_type(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1")
    old_diesel = await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    old_gasoline = await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.00"),
    )

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "21.50"}]},
    )

    assert response.status_code == 201

    old_diesel_row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == old_diesel.id)
    )
    assert old_diesel_row.is_latest is False

    old_gasoline_row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == old_gasoline.id)
    )
    assert old_gasoline_row.is_latest is True

    new_diesel_row = await db.fetch_one(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.DIESEL,
            PriceRegistration.is_latest.is_(True),
        )
    )
    assert new_diesel_row.price == Decimal("21.50")


async def test_register_prices_rejects_price_below_min(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "9.99"}]},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "greater_than_equal"
    assert error["msg"] == "Input should be greater than or equal to 10"


async def test_register_prices_rejects_price_above_max(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "40.01"}]},
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "less_than_equal"
    assert error["msg"] == "Input should be less than or equal to 40"


async def test_register_prices_rejects_duplicate_fuel_types(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1")

    response = await client.post(
        f"/stations/{station.id}/prices",
        json={
            "registrations": [
                {"fuelType": FuelType.DIESEL, "price": "20.00"},
                {"fuelType": FuelType.DIESEL, "price": "21.00"},
            ]
        },
    )

    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "value_error"
    assert error["msg"] == "Value error, Duplicate fuel types are not allowed"


async def test_register_prices_does_not_affect_other_stations(
    client: AsyncClient, db: DBSession
) -> None:
    s1 = await station_factory(db, osm_id="node/1")
    s2 = await station_factory(db, osm_id="node/2", lat=59.920, lng=10.760)
    other = await price_update_factory(
        db, station_id=s2.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )

    await client.post(
        f"/stations/{s1.id}/prices",
        json={"registrations": [{"fuelType": FuelType.DIESEL, "price": "21.50"}]},
    )

    row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == other.id)
    )
    assert row.is_latest is True
