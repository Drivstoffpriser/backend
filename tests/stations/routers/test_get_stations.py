from httpx import AsyncClient

from app.core.db import DBSession
from app.stations.enums import ProviderType
from tests.stations.factories import station_factory

# User location: central Oslo
USER_LAT = 59.911
USER_LNG = 10.752


async def test_get_stations_returns_stations(
    client: AsyncClient, db: DBSession
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
        "/stations/", params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000}
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


async def test_get_stations_empty(client: AsyncClient) -> None:
    response = await client.get(
        "/stations/", params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000}
    )

    assert response.status_code == 200
    assert response.json() == {"stations": []}


async def test_get_stations_filters_by_distance(
    client: AsyncClient, db: DBSession
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
        "/stations/", params={"lat": USER_LAT, "lng": USER_LNG, "distance": 5_000}
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["osmId"] == "node/near"


async def test_get_stations_ordered_by_distance(
    client: AsyncClient, db: DBSession
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
        "/stations/", params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000}
    )

    stations = response.json()["stations"]
    assert len(stations) == 2
    assert stations[0]["osmId"] == "node/near"
    assert stations[1]["osmId"] == "node/far"
