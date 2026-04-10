from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import station_factory


async def test_search_returns_matching_stations(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s = await station_factory(
        db, external_id="node/1", name="Shell Majorstuen", lat=59.911, lng=10.752
    )
    await station_factory(
        db, external_id="node/2", name="Rema 1000 Grünerløkka", lat=59.920, lng=10.760
    )

    response = await client.get(
        "/stations/search",
        params={"query": "Shell"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["id"] == str(s.id)
    assert stations[0]["name"] == "Shell Majorstuen"


async def test_search_returns_station_fields_without_prices(
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

    response = await client.get(
        "/stations/search",
        params={"query": "Circle K"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    station = response.json()["stations"][0]
    assert station["id"] == str(s.id)
    assert station["externalId"] == "node/1"
    assert station["name"] == "Circle K Majorstuen"
    assert station["address"] == "Bogstadveien 1"
    assert station["city"] == "Oslo"
    assert station["location"] == {"lat": 59.911, "lng": 10.752}
    assert "prices" not in station


async def test_search_orders_by_similarity(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await station_factory(
        db, external_id="node/1", name="Shell Majorstuen", lat=59.911, lng=10.752
    )
    await station_factory(
        db, external_id="node/2", name="Shell", lat=59.920, lng=10.760
    )

    response = await client.get(
        "/stations/search",
        params={"query": "Shell"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 2
    # Exact match "Shell" should rank higher than "Shell Majorstuen"
    assert stations[0]["name"] == "Shell"
    assert stations[1]["name"] == "Shell Majorstuen"


async def test_search_returns_empty_when_no_match(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await station_factory(
        db, external_id="node/1", name="Shell Majorstuen", lat=59.911, lng=10.752
    )

    response = await client.get(
        "/stations/search",
        params={"query": "xyzzy"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    assert response.json()["stations"] == []


async def test_search_is_case_insensitive(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s = await station_factory(
        db, external_id="node/1", name="Shell Majorstuen", lat=59.911, lng=10.752
    )

    response = await client.get(
        "/stations/search",
        params={"query": "shell majorstuen"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    stations = response.json()["stations"]
    assert len(stations) == 1
    assert stations[0]["id"] == str(s.id)


async def test_search_requires_query_param(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get(
        "/stations/search",
        authenticate_with=unverified_user,
    )
    assert response.status_code == 422


async def test_search_requires_non_empty_query(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get(
        "/stations/search",
        params={"query": ""},
        authenticate_with=unverified_user,
    )
    assert response.status_code == 422


async def test_search_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.get(
        "/stations/search",
        params={"query": "Shell"},
    )
    assert response.status_code == 401


async def test_search_limits_to_20_results(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    for i in range(25):
        await station_factory(
            db,
            external_id=f"node/{i}",
            name=f"Shell Station {i}",
            address=f"Street {i}",
            lat=59.911 + i * 0.001,
            lng=10.752 + i * 0.001,
        )

    response = await client.get(
        "/stations/search",
        params={"query": "Shell"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    assert len(response.json()["stations"]) == 20
