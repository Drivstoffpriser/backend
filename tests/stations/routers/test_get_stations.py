from datetime import UTC, datetime
from decimal import Decimal

from app.core.db import DBSession
from app.stations.enums import FuelType, ProviderType
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory

# User location: central Oslo
USER_LAT = 59.911
USER_LNG = 10.752


async def test_get_stations_returns_stations(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s1 = await station_factory(
        db,
        osm_id="node/1",
        name="Shell Majorstuen",
        provider=ProviderType.ST1,
        address="Bogstadveien 1",
        city="Oslo",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        osm_id="node/2",
        name="Circle K Grünerløkka",
        address="Grünerløkka 1",
        lat=59.920,
        lng=10.760,
    )

    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 2

    by_osm_id = {s["osmId"]: s for s in stations}
    station = by_osm_id["node/1"]
    assert station["id"] == str(s1.id)
    assert station["osmId"] == "node/1"
    assert station["name"] == "Shell Majorstuen"
    assert station["provider"] == "ST1"
    assert station["address"] == "Bogstadveien 1"
    assert station["city"] == "Oslo"
    assert station["location"] == {"lat": 59.911, "lng": 10.752}
    assert station["prices"] == []


async def test_get_stations_empty(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    assert response.json() == {"stations": []}


async def test_get_stations_filters_by_distance(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await station_factory(
        db,
        osm_id="node/near",
        name="Nearby Station",
        address="Near St 1",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        osm_id="node/far",
        name="Faraway Station",
        address="Far St 1",
        lat=61.0,  # ~120 km north
        lng=10.752,
    )

    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 5_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["osmId"] == "node/near"


async def test_get_stations_ordered_by_distance(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # ~1.1 km north of user
    await station_factory(
        db,
        osm_id="node/far",
        name="Far Station",
        address="Far St 1",
        lat=59.921,
        lng=10.752,
    )
    # ~100 m north of user
    await station_factory(
        db,
        osm_id="node/near",
        name="Near Station",
        address="Near St 1",
        lat=59.912,
        lng=10.752,
    )

    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    stations = response.json()["stations"]
    assert len(stations) == 2
    assert stations[0]["osmId"] == "node/near"
    assert stations[1]["osmId"] == "node/far"


async def test_get_stations_includes_latest_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, osm_id="node/1")

    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

    # Insert an older and a newer DIESEL price — only the newer should appear
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=t1,
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("21.50"),
        registered_at=t2,
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.90"),
        registered_at=t2,
    )

    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1

    prices = {p["fuelType"]: p for p in stations[0]["prices"]}
    assert len(prices) == 2
    assert prices["DIESEL"]["price"] == "21.50"
    assert prices["GASOLINE_95"]["price"] == "22.90"
    assert "GASOLINE_98" not in prices


async def test_get_stations_only_includes_prices_for_own_station(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s1 = await station_factory(db, osm_id="node/1", lat=59.911, lng=10.752)
    s2 = await station_factory(db, osm_id="node/2", lat=59.912, lng=10.752)

    await price_update_factory(
        db, station_id=s1.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db, station_id=s2.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )

    response = await client.get(
        "/stations/",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    by_osm_id = {s["osmId"]: s for s in response.json()["stations"]}

    assert by_osm_id["node/1"]["prices"][0]["price"] == "20.00"
    assert by_osm_id["node/2"]["prices"][0]["price"] == "25.00"
