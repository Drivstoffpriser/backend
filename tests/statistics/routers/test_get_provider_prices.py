from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.db import DBSession
from app.stations.enums import FuelType, ProviderType
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory


async def test_empty_database(client: AuthenticatedClient) -> None:
    response = await client.get("/statistics/provider-prices")

    assert response.status_code == 200
    assert response.json() == {"last30d": {}, "last24h": {}}


async def test_returns_daily_averages_per_provider_and_fuel_type(
    client: AuthenticatedClient, db: DBSession
) -> None:
    now = datetime.now(UTC)
    station_a = await station_factory(
        db, external_id="node/a", provider=ProviderType.CIRCLE_K, lat=59.911, lng=10.752
    )
    station_b = await station_factory(
        db, external_id="node/b", provider=ProviderType.CIRCLE_K, lat=59.912, lng=10.753
    )

    # Two CIRCLE_K stations both register diesel on the same day → average
    await price_update_factory(
        db,
        station_id=station_a.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("18.00"),
        registered_at=now - timedelta(days=1),
    )
    await price_update_factory(
        db,
        station_id=station_b.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(days=1),
    )

    response = await client.get("/statistics/provider-prices")

    assert response.status_code == 200
    data = response.json()["last30d"]
    circle_k_diesel = data["CIRCLE_K"]["DIESEL"]
    assert len(circle_k_diesel) == 1
    assert circle_k_diesel[0]["averagePrice"] == "19.00"


async def test_filters_to_last_30_days(
    client: AuthenticatedClient, db: DBSession
) -> None:
    now = datetime.now(UTC)
    station = await station_factory(
        db, external_id="node/1", provider=ProviderType.UNO_X
    )

    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(days=10),
    )
    # Older than 30 days — must not appear
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.00"),
        registered_at=now - timedelta(days=40),
    )

    response = await client.get("/statistics/provider-prices")

    assert response.status_code == 200
    data = response.json()["last30d"]
    assert "UNO_X" in data
    assert "DIESEL" in data["UNO_X"]
    assert "GASOLINE_95" not in data.get("UNO_X", {})


async def test_multiple_providers_returned_separately(
    client: AuthenticatedClient, db: DBSession
) -> None:
    now = datetime.now(UTC)
    circle_k_station = await station_factory(
        db,
        external_id="node/ck",
        provider=ProviderType.CIRCLE_K,
        lat=59.911,
        lng=10.752,
    )
    uno_x_station = await station_factory(
        db, external_id="node/ux", provider=ProviderType.UNO_X, lat=59.920, lng=10.760
    )

    await price_update_factory(
        db,
        station_id=circle_k_station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("19.00"),
        registered_at=now - timedelta(days=2),
    )
    await price_update_factory(
        db,
        station_id=uno_x_station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("17.50"),
        registered_at=now - timedelta(days=2),
    )

    response = await client.get("/statistics/provider-prices")

    assert response.status_code == 200
    data = response.json()["last30d"]
    assert data["CIRCLE_K"]["DIESEL"][0]["averagePrice"] == "19.00"
    assert data["UNO_X"]["DIESEL"][0]["averagePrice"] == "17.50"


async def test_last_24h_returns_average_without_date(
    client: AuthenticatedClient, db: DBSession
) -> None:
    now = datetime.now(UTC)
    station_a = await station_factory(
        db, external_id="node/a", provider=ProviderType.CIRCLE_K, lat=59.911, lng=10.752
    )
    station_b = await station_factory(
        db, external_id="node/b", provider=ProviderType.CIRCLE_K, lat=59.912, lng=10.753
    )

    await price_update_factory(
        db,
        station_id=station_a.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("18.00"),
        registered_at=now - timedelta(hours=6),
    )
    await price_update_factory(
        db,
        station_id=station_b.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(hours=12),
    )
    # Older than 24h — must not appear in last_24h
    await price_update_factory(
        db,
        station_id=station_a.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.00"),
        registered_at=now - timedelta(days=5),
    )

    response = await client.get("/statistics/provider-prices")

    assert response.status_code == 200
    body = response.json()
    last_24h = body["last24h"]
    assert last_24h["CIRCLE_K"]["DIESEL"] == "19.00"
    assert "GASOLINE_95" not in last_24h.get("CIRCLE_K", {})
    # The 5-day-old entry should still appear in last_30d
    assert "GASOLINE_95" in body["last30d"].get("CIRCLE_K", {})
