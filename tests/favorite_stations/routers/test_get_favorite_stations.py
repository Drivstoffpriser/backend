from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.favorite_stations.factories import favorite_station_factory
from tests.stations.factories import station_factory
from tests.users.factories import user_factory


async def test_get_favorites_empty(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.get("/favorites", authenticate_with=unverified_user)

    assert response.status_code == 200
    assert response.json() == {"stationIds": []}


async def test_get_favorites_returns_station_ids(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    s1 = await station_factory(
        db, external_id="node/1", name="Station 1", address="Addr 1"
    )
    s2 = await station_factory(
        db,
        external_id="node/2",
        name="Station 2",
        address="Addr 2",
        lat=59.920,
        lng=10.760,
    )

    await favorite_station_factory(db, user_id=unverified_user.id, station_id=s1.id)
    await favorite_station_factory(db, user_id=unverified_user.id, station_id=s2.id)

    response = await client.get("/favorites", authenticate_with=unverified_user)

    assert response.status_code == 200
    assert set(response.json()["stationIds"]) == {str(s1.id), str(s2.id)}


async def test_get_favorites_does_not_return_other_users_favorites(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    other_user = await user_factory(
        db=db, firebase_uid="other", email="other@example.com"
    )
    station = await station_factory(
        db, external_id="node/1", name="Station 1", address="Addr 1"
    )

    await favorite_station_factory(db, user_id=other_user.id, station_id=station.id)

    response = await client.get("/favorites", authenticate_with=unverified_user)

    assert response.status_code == 200
    assert response.json() == {"stationIds": []}
