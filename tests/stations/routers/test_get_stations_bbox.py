from decimal import Decimal

from httpx import AsyncClient

from app.core.db import DBSession
from app.stations.enums import FuelType, ProviderType
from tests.stations.factories import price_update_factory, station_factory

BBOX_PARAMS = {
    "min_lat": 59.90,
    "min_lng": 10.70,
    "max_lat": 59.93,
    "max_lng": 10.80,
}


async def test_get_stations_bbox_returns_stations(
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

    response = await client.get("/stations/bbox", params=BBOX_PARAMS)

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    station = stations[0]
    assert station["id"] == str(s1.id)
    assert station["osmId"] == "node/1"
    assert station["name"] == "Shell Majorstuen"
    assert station["provider"] == "ST1"
    assert station["address"] == "Bogstadveien 1"
    assert station["city"] == "Oslo"
    assert station["location"] == {"lat": 59.911, "lng": 10.752}


async def test_get_stations_bbox_empty(client: AsyncClient) -> None:
    response = await client.get("/stations/bbox", params=BBOX_PARAMS)

    assert response.status_code == 200
    assert response.json() == {"stations": []}


async def test_get_stations_bbox_filters_by_bounds(
    client: AsyncClient, db: DBSession
) -> None:
    await station_factory(
        db,
        osm_id="node/inside",
        name="Inside Station",
        address="Inside St 1",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        osm_id="node/outside",
        name="Outside Station",
        address="Outside St 1",
        lat=61.0,  # well north of bbox
        lng=10.752,
    )

    response = await client.get("/stations/bbox", params=BBOX_PARAMS)

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["osmId"] == "node/inside"


async def test_get_stations_bbox_includes_prices(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1", lat=59.911, lng=10.752)
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.90"),
    )

    response = await client.get("/stations/bbox", params=BBOX_PARAMS)

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    prices = {p["fuelType"]: p for p in stations[0]["prices"]}
    assert prices[FuelType.DIESEL]["price"] == "20.00"
    assert prices[FuelType.GASOLINE_95]["price"] == "22.90"


async def test_get_stations_bbox_only_returns_latest_prices(
    client: AsyncClient, db: DBSession
) -> None:
    station = await station_factory(db, osm_id="node/1", lat=59.911, lng=10.752)
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("19.00")
    )
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.50")
    )

    response = await client.get("/stations/bbox", params=BBOX_PARAMS)

    assert response.status_code == 200
    prices = response.json()["stations"][0]["prices"]
    assert len(prices) == 1
    assert prices[0]["fuelType"] == FuelType.DIESEL
    assert prices[0]["price"] == "20.50"
