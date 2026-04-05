from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import station_factory


async def test_add_favorite(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(
        db, osm_id="node/1", name="Station 1", address="Addr 1"
    )

    response = await client.post(
        "/favorites",
        json={"station_id": str(station.id)},
        authenticate_with=verified_user,
    )

    assert response.status_code == 201

    favorites = await client.get("/favorites", authenticate_with=verified_user)
    assert favorites.json() == [str(station.id)]


async def test_add_favorite_is_idempotent(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(
        db, osm_id="node/1", name="Station 1", address="Addr 1"
    )

    # Add the same station twice
    await client.post(
        "/favorites",
        json={"station_id": str(station.id)},
        authenticate_with=verified_user,
    )
    response = await client.post(
        "/favorites",
        json={"station_id": str(station.id)},
        authenticate_with=verified_user,
    )

    assert response.status_code == 201

    favorites = await client.get("/favorites", authenticate_with=verified_user)
    assert favorites.json() == [str(station.id)]
