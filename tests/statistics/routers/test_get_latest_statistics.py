from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.db import DBSession
from app.stations.enums import FuelType
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory

USER_LAT = 59.911
USER_LNG = 10.752


async def test_latest_empty_database(client: AuthenticatedClient) -> None:
    response = await client.get("/statistics/latest")

    assert response.status_code == 200
    data = response.json()
    assert data["allStations"] == {}
    assert data["activity"] == {"last24Hours": 0, "last7Days": 0, "last30Days": 0}


async def test_latest_returns_all_stations_extremes(
    client: AuthenticatedClient, db: DBSession
) -> None:
    cheap = await station_factory(
        db, external_id="node/cheap", name="Cheap Station", lat=59.911, lng=10.752
    )
    expensive = await station_factory(
        db,
        external_id="node/expensive",
        name="Expensive Station",
        lat=59.912,
        lng=10.753,
    )

    await price_update_factory(
        db, station_id=cheap.id, fuel_type=FuelType.DIESEL, price=Decimal("17.00")
    )
    await price_update_factory(
        db, station_id=expensive.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )
    await price_update_factory(
        db, station_id=cheap.id, fuel_type=FuelType.GASOLINE_95, price=Decimal("18.00")
    )
    await price_update_factory(
        db,
        station_id=expensive.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("26.00"),
    )

    response = await client.get("/statistics/latest")

    assert response.status_code == 200
    extremes = response.json()["allStations"]

    assert extremes["DIESEL"]["lowestPrice"] == "17.00"
    assert extremes["DIESEL"]["lowestStationName"] == "Cheap Station"
    assert extremes["DIESEL"]["highestPrice"] == "25.00"
    assert extremes["DIESEL"]["highestStationName"] == "Expensive Station"

    assert extremes["GASOLINE_95"]["lowestPrice"] == "18.00"
    assert extremes["GASOLINE_95"]["highestPrice"] == "26.00"


async def test_latest_activity_counts_by_time_window(
    client: AuthenticatedClient, db: DBSession
) -> None:
    now = datetime.now(UTC)
    station = await station_factory(db, external_id="node/1")

    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(hours=1),
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("21.00"),
        registered_at=now - timedelta(days=3),
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_98,
        price=Decimal("22.00"),
        registered_at=now - timedelta(days=15),
    )
    # Older than 30 days — not counted
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("19.00"),
        registered_at=now - timedelta(days=40),
    )

    response = await client.get("/statistics/latest")

    assert response.status_code == 200
    activity = response.json()["activity"]
    assert activity["last24Hours"] == 1
    assert activity["last7Days"] == 2
    assert activity["last30Days"] == 3


async def test_nearest_returns_extremes_among_multiple_nearby_stations(
    client: AuthenticatedClient, db: DBSession
) -> None:
    cheap = await station_factory(
        db, external_id="node/cheap", name="Cheap Station", lat=USER_LAT, lng=USER_LNG
    )
    expensive = await station_factory(
        db,
        external_id="node/expensive",
        name="Expensive Station",
        lat=USER_LAT + 0.001,
        lng=USER_LNG,
    )

    await price_update_factory(
        db, station_id=cheap.id, fuel_type=FuelType.DIESEL, price=Decimal("17.00")
    )
    await price_update_factory(
        db, station_id=expensive.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )

    response = await client.get(
        "/statistics/nearest",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
    )

    assert response.status_code == 200
    nearby = response.json()["nearbyStations"]
    assert nearby["DIESEL"]["lowestPrice"] == "17.00"
    assert nearby["DIESEL"]["lowestStationName"] == "Cheap Station"
    assert nearby["DIESEL"]["highestPrice"] == "25.00"
    assert nearby["DIESEL"]["highestStationName"] == "Expensive Station"


async def test_nearest_requires_location(client: AuthenticatedClient) -> None:
    response = await client.get("/statistics/nearest")
    assert response.status_code == 422


async def test_nearest_empty_when_no_nearby_stations(
    client: AuthenticatedClient, db: DBSession
) -> None:
    far = await station_factory(db, external_id="node/far", lat=61.0, lng=USER_LNG)
    await price_update_factory(
        db, station_id=far.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )

    response = await client.get(
        "/statistics/nearest",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
    )

    assert response.status_code == 200
    assert response.json()["nearbyStations"] == {}


async def test_latest_excludes_non_latest_prices(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/1", name="Station")

    # First registration — will be demoted to is_latest=False
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )
    # Second registration — is_latest=True, old price should be ignored
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("17.00")
    )

    response = await client.get("/statistics/latest")

    assert response.status_code == 200
    diesel = response.json()["allStations"]["DIESEL"]
    assert diesel["lowestPrice"] == "17.00"
    assert diesel["highestPrice"] == "17.00"


async def test_nearest_excludes_non_latest_prices(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(
        db, external_id="node/1", name="Station", lat=USER_LAT, lng=USER_LNG
    )

    # First registration — will be demoted to is_latest=False
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )
    # Second registration — is_latest=True, old price should be ignored
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("17.00")
    )

    response = await client.get(
        "/statistics/nearest",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
    )

    assert response.status_code == 200
    diesel = response.json()["nearbyStations"]["DIESEL"]
    assert diesel["lowestPrice"] == "17.00"
    assert diesel["highestPrice"] == "17.00"


async def test_nearest_rejects_zero_distance(client: AuthenticatedClient) -> None:
    response = await client.get(
        "/statistics/nearest",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 0},
    )
    assert response.status_code == 422


async def test_nearest_filters_by_distance(
    client: AuthenticatedClient, db: DBSession
) -> None:
    near = await station_factory(
        db, external_id="node/near", name="Near Station", lat=USER_LAT, lng=USER_LNG
    )
    far = await station_factory(
        db, external_id="node/far", name="Far Station", lat=61.0, lng=USER_LNG
    )

    await price_update_factory(
        db, station_id=near.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db, station_id=far.id, fuel_type=FuelType.DIESEL, price=Decimal("15.00")
    )

    response = await client.get(
        "/statistics/nearest",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
    )

    assert response.status_code == 200
    nearby = response.json()["nearbyStations"]
    assert nearby["DIESEL"]["lowestPrice"] == "20.00"
    assert nearby["DIESEL"]["lowestStationName"] == "Near Station"
    assert nearby["DIESEL"]["highestPrice"] == "20.00"
    assert nearby["DIESEL"]["highestStationName"] == "Near Station"
