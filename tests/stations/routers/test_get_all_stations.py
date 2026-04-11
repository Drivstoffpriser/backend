from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import station_factory


async def test_get_all_returns_all_stations(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s1 = await station_factory(
        db, external_id="node/1", name="Shell Majorstuen", lat=59.911, lng=10.752
    )
    s2 = await station_factory(
        db, external_id="node/2", name="Circle K Grünerløkka", lat=59.920, lng=10.760
    )

    response = await client.get("/stations/all", authenticate_with=unverified_user)

    assert response.status_code == 200
    ids = {s["id"] for s in response.json()["stations"]}
    assert str(s1.id) in ids
    assert str(s2.id) in ids


async def test_get_all_returns_station_fields_without_prices(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s = await station_factory(
        db,
        external_id="node/1",
        name="Circle K Majorstuen",
        address="Bogstadveien 1",
        city="Oslo",
        lat=59.911,
        lng=10.752,
    )

    response = await client.get("/stations/all", authenticate_with=unverified_user)

    assert response.status_code == 200
    station = next(x for x in response.json()["stations"] if x["id"] == str(s.id))
    assert station["externalId"] == "node/1"
    assert station["name"] == "Circle K Majorstuen"
    assert station["address"] == "Bogstadveien 1"
    assert station["city"] == "Oslo"
    assert station["location"] == {"lat": 59.911, "lng": 10.752}
    assert "prices" not in station


async def test_get_all_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.get("/stations/all")
    assert response.status_code == 401
