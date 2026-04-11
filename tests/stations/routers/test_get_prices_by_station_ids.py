from decimal import Decimal
from uuid import uuid4

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory


async def test_get_prices_single_station(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )

    response = await client.get(
        f"/stations/prices?stationIds={station.id}",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["stationId"] == str(station.id)
    prices = stations[0]["prices"]
    assert len(prices) == 1
    assert prices[0]["fuelType"] == FuelType.DIESEL
    assert prices[0]["price"] == "20.00"
    assert prices[0]["registeredAt"] is not None


async def test_get_prices_multiple_stations(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station1 = await station_factory(db, external_id="node/1", lat=59.911, lng=10.752)
    station2 = await station_factory(db, external_id="node/2", lat=59.912, lng=10.753)
    await price_update_factory(
        db, station_id=station1.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db,
        station_id=station2.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("25.00"),
    )

    response = await client.get(
        f"/stations/prices?stationIds={station1.id}&stationIds={station2.id}",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 2
    by_id = {s["stationId"]: s for s in stations}
    assert any(
        p["fuelType"] == FuelType.DIESEL for p in by_id[str(station1.id)]["prices"]
    )
    assert any(
        p["fuelType"] == FuelType.GASOLINE_95 for p in by_id[str(station2.id)]["prices"]
    )


async def test_get_prices_station_without_prices_returns_estimates(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # Station with no prices — needs a nearby station for estimates to work
    station_with_price = await station_factory(
        db, external_id="node/1", lat=59.911, lng=10.752
    )
    station_no_price = await station_factory(
        db, external_id="node/2", lat=59.912, lng=10.753
    )
    await price_update_factory(
        db,
        station_id=station_with_price.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
    )

    response = await client.get(
        f"/stations/prices?stationIds={station_no_price.id}",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    prices = stations[0]["prices"]
    # Should have estimated price with registeredAt=None
    assert len(prices) > 0
    diesel_prices = [p for p in prices if p["fuelType"] == FuelType.DIESEL]
    assert len(diesel_prices) == 1
    assert diesel_prices[0]["registeredAt"] is None


async def test_get_prices_nonexistent_station_id_returns_empty_prices(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    fake_id = uuid4()

    response = await client.get(
        f"/stations/prices?stationIds={fake_id}",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["stationId"] == str(fake_id)
    assert stations[0]["prices"] == []


async def test_get_prices_requires_auth(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.get(f"/stations/prices?stationIds={station.id}")

    assert response.status_code == 401
