from decimal import Decimal

from app.core.db import DBSession
from app.stations.enums import FuelType, ProviderType
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory

BBOX_PARAMS = {
    "minLat": 59.90,
    "minLng": 10.70,
    "maxLat": 59.93,
    "maxLng": 10.80,
}


async def test_get_stations_bbox_returns_stations(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s1 = await station_factory(
        db,
        external_id="node/1",
        name="Shell Majorstuen",
        provider=ProviderType.ST1,
        address="Bogstadveien 1",
        city="Oslo",
        lat=59.911,
        lng=10.752,
    )

    response = await client.get(
        "/stations/bbox", params=BBOX_PARAMS, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    station = stations[0]
    assert station["id"] == str(s1.id)
    assert station["externalId"] == "node/1"
    assert station["name"] == "Shell Majorstuen"
    assert station["provider"] == "ST1"
    assert station["address"] == "Bogstadveien 1"
    assert station["city"] == "Oslo"
    assert station["location"] == {"lat": 59.911, "lng": 10.752}


async def test_get_stations_bbox_empty(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get(
        "/stations/bbox", params=BBOX_PARAMS, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    assert response.json() == {"stations": []}


async def test_get_stations_bbox_filters_by_bounds(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await station_factory(
        db,
        external_id="node/inside",
        name="Inside Station",
        address="Inside St 1",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        external_id="node/outside",
        name="Outside Station",
        address="Outside St 1",
        lat=61.0,  # well north of bbox
        lng=10.752,
    )

    response = await client.get(
        "/stations/bbox", params=BBOX_PARAMS, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["externalId"] == "node/inside"


async def test_get_stations_bbox_includes_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1", lat=59.911, lng=10.752)
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("22.90"),
    )

    response = await client.get(
        "/stations/bbox", params=BBOX_PARAMS, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    prices = {p["fuelType"]: p for p in stations[0]["prices"]}
    assert prices[FuelType.DIESEL]["price"] == "20.00"
    assert prices[FuelType.GASOLINE_95]["price"] == "22.90"


async def test_get_stations_bbox_only_returns_latest_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1", lat=59.911, lng=10.752)
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("19.00")
    )
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.50")
    )

    response = await client.get(
        "/stations/bbox", params=BBOX_PARAMS, authenticate_with=unverified_user
    )

    assert response.status_code == 200
    prices = response.json()["stations"][0]["prices"]
    assert len(prices) == 1
    assert prices[0]["fuelType"] == FuelType.DIESEL
    assert prices[0]["price"] == "20.50"
