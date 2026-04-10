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
        external_id="node/1",
        name="Shell Majorstuen",
        provider=ProviderType.ST1,
        address="Bogstadveien 1",
        city="Oslo",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        external_id="node/2",
        name="Circle K Grünerløkka",
        address="Grünerløkka 1",
        lat=59.920,
        lng=10.760,
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 2

    by_external_id = {s["externalId"]: s for s in stations}
    station = by_external_id["node/1"]
    assert station["id"] == str(s1.id)
    assert station["externalId"] == "node/1"
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
        "/stations",
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
        external_id="node/near",
        name="Nearby Station",
        address="Near St 1",
        lat=59.911,
        lng=10.752,
    )
    await station_factory(
        db,
        external_id="node/far",
        name="Faraway Station",
        address="Far St 1",
        lat=61.0,  # ~120 km north
        lng=10.752,
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 5_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["externalId"] == "node/near"


async def test_get_stations_ordered_by_distance(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # ~1.1 km north of user
    await station_factory(
        db,
        external_id="node/far",
        name="Far Station",
        address="Far St 1",
        lat=59.921,
        lng=10.752,
    )
    # ~100 m north of user
    await station_factory(
        db,
        external_id="node/near",
        name="Near Station",
        address="Near St 1",
        lat=59.912,
        lng=10.752,
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    stations = response.json()["stations"]
    assert len(stations) == 2
    assert stations[0]["externalId"] == "node/near"
    assert stations[1]["externalId"] == "node/far"


async def test_get_stations_includes_latest_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

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
        "/stations",
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
    s1 = await station_factory(db, external_id="node/1", lat=59.911, lng=10.752)
    s2 = await station_factory(db, external_id="node/2", lat=59.912, lng=10.752)

    await price_update_factory(
        db, station_id=s1.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db, station_id=s2.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    by_external_id = {s["externalId"]: s for s in response.json()["stations"]}

    assert by_external_id["node/1"]["prices"][0]["price"] == "20.00"
    assert by_external_id["node/2"]["prices"][0]["price"] == "25.00"


async def test_get_stations_estimates_prices_for_station_without_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # Station without prices — should get estimates from nearby priced stations
    await station_factory(db, external_id="node/target", lat=59.911, lng=10.752)
    neighbor1 = await station_factory(
        db, external_id="node/n1", address="N1", lat=59.912, lng=10.752
    )
    neighbor2 = await station_factory(
        db, external_id="node/n2", address="N2", lat=59.913, lng=10.752
    )

    await price_update_factory(
        db, station_id=neighbor1.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    await price_update_factory(
        db, station_id=neighbor2.id, fuel_type=FuelType.DIESEL, price=Decimal("22.00")
    )
    await price_update_factory(
        db,
        station_id=neighbor1.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("24.00"),
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    by_external_id = {s["externalId"]: s for s in response.json()["stations"]}
    target_prices = {p["fuelType"]: p for p in by_external_id["node/target"]["prices"]}

    # DIESEL: avg of 20.00 and 22.00 = 21.00
    assert target_prices["DIESEL"]["price"] == "21.00"
    assert target_prices["DIESEL"]["registeredAt"] is None

    # GASOLINE_95: only one neighbor has it, so estimate is 24.00
    assert target_prices["GASOLINE_95"]["price"] == "24.00"
    assert target_prices["GASOLINE_95"]["registeredAt"] is None

    # GASOLINE_98: never estimated
    assert "GASOLINE_98" not in target_prices


async def test_get_stations_real_prices_unaffected_by_estimation(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # Station with real prices — should NOT get estimates mixed in
    priced = await station_factory(
        db, external_id="node/priced", lat=59.911, lng=10.752
    )
    neighbor = await station_factory(
        db, external_id="node/neighbor", address="N1", lat=59.912, lng=10.752
    )

    await price_update_factory(
        db, station_id=priced.id, fuel_type=FuelType.DIESEL, price=Decimal("19.00")
    )
    await price_update_factory(
        db, station_id=neighbor.id, fuel_type=FuelType.DIESEL, price=Decimal("25.00")
    )
    await price_update_factory(
        db,
        station_id=neighbor.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("26.00"),
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    by_external_id = {s["externalId"]: s for s in response.json()["stations"]}
    priced_prices = {p["fuelType"]: p for p in by_external_id["node/priced"]["prices"]}

    # Only the real DIESEL price — no GASOLINE_95 estimate leaking in
    assert set(priced_prices.keys()) == {"DIESEL"}
    assert priced_prices["DIESEL"]["price"] == "19.00"
    assert priced_prices["DIESEL"]["registeredAt"] is not None


async def test_get_stations_only_estimates_diesel_and_gasoline_95(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # Estimation should only cover DIESEL and GASOLINE_95, not GASOLINE_98
    await station_factory(db, external_id="node/target", lat=59.911, lng=10.752)
    neighbor = await station_factory(
        db, external_id="node/neighbor", address="N1", lat=59.912, lng=10.752
    )

    await price_update_factory(
        db,
        station_id=neighbor.id,
        fuel_type=FuelType.GASOLINE_98,
        price=Decimal("28.00"),
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    by_external_id = {s["externalId"]: s for s in response.json()["stations"]}
    assert by_external_id["node/target"]["prices"] == []


async def test_get_stations_no_estimate_when_no_priced_neighbors(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    # Station without prices and no nearby priced stations — prices should be empty
    await station_factory(db, external_id="node/lonely", lat=59.911, lng=10.752)

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000},
        authenticate_with=unverified_user,
    )

    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["prices"] == []


async def test_sort_nearest_orders_by_distance(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await station_factory(db, external_id="node/far", lat=59.921, lng=10.752)
    await station_factory(db, external_id="node/near", lat=59.912, lng=10.752)

    response = await client.get(
        "/stations",
        params={
            "lat": USER_LAT,
            "lng": USER_LNG,
            "distance": 10_000,
            "sort": "nearest",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert [s["externalId"] for s in stations] == ["node/near", "node/far"]


async def test_sort_cheapest_orders_by_price_for_fuel_type(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s_cheap = await station_factory(
        db, external_id="node/cheap", lat=59.911, lng=10.752
    )
    s_expensive = await station_factory(
        db, external_id="node/expensive", lat=59.912, lng=10.752
    )
    s_cheapest = await station_factory(
        db, external_id="node/cheapest", lat=59.913, lng=10.752
    )

    await price_update_factory(
        db, station_id=s_cheap.id, fuel_type=FuelType.DIESEL, price=Decimal("18.00")
    )
    await price_update_factory(
        db, station_id=s_expensive.id, fuel_type=FuelType.DIESEL, price=Decimal("23.00")
    )
    await price_update_factory(
        db, station_id=s_cheapest.id, fuel_type=FuelType.DIESEL, price=Decimal("17.00")
    )

    response = await client.get(
        "/stations",
        params={
            "lat": USER_LAT,
            "lng": USER_LNG,
            "distance": 10_000,
            "sort": "cheapest",
            "fuelType": "DIESEL",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert [s["externalId"] for s in stations] == [
        "node/cheapest",
        "node/cheap",
        "node/expensive",
    ]


async def test_sort_cheapest_puts_stations_without_price_last(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s_no_price = await station_factory(
        db, external_id="node/no-price", lat=59.911, lng=10.752
    )
    s_priced = await station_factory(
        db, external_id="node/priced", lat=59.912, lng=10.752
    )

    await price_update_factory(
        db, station_id=s_priced.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    # s_no_price has GASOLINE_95 but not DIESEL — should sort last for fuelType=DIESEL
    await price_update_factory(
        db,
        station_id=s_no_price.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("15.00"),
    )

    response = await client.get(
        "/stations",
        params={
            "lat": USER_LAT,
            "lng": USER_LNG,
            "distance": 10_000,
            "sort": "cheapest",
            "fuelType": "DIESEL",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert [s["externalId"] for s in stations] == ["node/priced", "node/no-price"]


async def test_sort_cheapest_requires_fuel_type(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get(
        "/stations",
        params={
            "lat": USER_LAT,
            "lng": USER_LNG,
            "distance": 10_000,
            "sort": "cheapest",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 422


async def test_sort_latest_orders_by_most_recent_price_update(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s_old = await station_factory(db, external_id="node/old", lat=59.911, lng=10.752)
    s_new = await station_factory(db, external_id="node/new", lat=59.912, lng=10.752)

    await price_update_factory(
        db,
        station_id=s_old.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    await price_update_factory(
        db,
        station_id=s_new.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime(2026, 1, 2, 12, 0, tzinfo=UTC),
    )

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000, "sort": "latest"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert [s["externalId"] for s in stations] == ["node/new", "node/old"]


async def test_sort_latest_puts_stations_without_prices_last(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s_no_prices = await station_factory(
        db, external_id="node/no-prices", lat=59.911, lng=10.752
    )
    s_priced = await station_factory(
        db, external_id="node/priced", lat=59.912, lng=10.752
    )

    await price_update_factory(
        db, station_id=s_priced.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )
    _ = s_no_prices  # registered but never given a price

    response = await client.get(
        "/stations",
        params={"lat": USER_LAT, "lng": USER_LNG, "distance": 10_000, "sort": "latest"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert [s["externalId"] for s in stations] == ["node/priced", "node/no-prices"]
