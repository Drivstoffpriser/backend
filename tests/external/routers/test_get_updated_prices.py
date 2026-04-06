from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient

from app.core.db import DBSession
from app.stations.enums import FuelType
from tests.external.factories import api_token_factory
from tests.stations.factories import price_update_factory, station_factory


async def test_returns_401_without_api_token(client: AsyncClient) -> None:
    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2020-01-01T00:00:00Z"},
    )
    assert response.status_code == 401


async def test_returns_401_with_invalid_token(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2020-01-01T00:00:00Z"},
        headers={"Authorization": "Bearer bad_token"},
    )
    assert response.status_code == 401


async def test_returns_401_with_inactive_token(
    client: AsyncClient, db: DBSession
) -> None:
    _, plaintext = await api_token_factory(db=db, is_active=False)
    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2020-01-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {plaintext}"},
    )
    assert response.status_code == 401


async def test_returns_stations_updated_since(
    client: AsyncClient, db: DBSession
) -> None:
    _, token = await api_token_factory(db=db)
    station = await station_factory(db=db, external_id="node/ext1")

    t_old = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    t_new = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=t_old,
    )

    # Station with no recent updates — create a separate one
    other = await station_factory(db, external_id="node/ext2", lat=60.0, lng=11.0)
    await price_update_factory(
        db,
        station_id=other.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("19.00"),
        registered_at=t_old,
    )

    # Update the first station recently
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("22.00"),
        registered_at=t_new,
    )

    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2026-01-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["stations"]) == 1
    assert data["stations"][0]["externalId"] == "node/ext1"

    prices = data["stations"][0]["prices"]
    assert len(prices) == 1
    assert prices[0]["fuelType"] == "DIESEL"
    assert prices[0]["price"] == "22.00"


async def test_returns_empty_when_nothing_updated(
    client: AsyncClient, db: DBSession
) -> None:
    _, token = await api_token_factory(db=db)
    station = await station_factory(db, external_id="node/ext3")
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime(2025, 1, 1, tzinfo=UTC),
    )

    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2026-06-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"stations": []}


async def test_returns_all_latest_prices_for_updated_station(
    client: AsyncClient, db: DBSession
) -> None:
    """All latest prices for the station are returned, not just the updated ones."""
    _, token = await api_token_factory(db=db)
    station = await station_factory(db, external_id="node/ext4")

    t_old = datetime(2025, 6, 1, tzinfo=UTC)
    t_new = datetime(2026, 3, 1, tzinfo=UTC)

    # Old gasoline price
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("23.00"),
        registered_at=t_old,
    )
    # New diesel price
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("21.00"),
        registered_at=t_new,
    )

    response = await client.get(
        "/external/prices",
        params={"updatedSince": "2026-01-01T00:00:00Z"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    prices = {p["fuelType"]: p for p in stations[0]["prices"]}
    assert len(prices) == 2
    assert prices["DIESEL"]["price"] == "21.00"
    assert prices["GASOLINE_95"]["price"] == "23.00"
