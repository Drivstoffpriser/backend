from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.favorite_stations.factories import favorite_station_factory
from tests.stations.factories import station_factory


async def test_remove_favorite(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(
        db, osm_id="node/1", name="Station 1", address="Addr 1"
    )
    await favorite_station_factory(db, user_id=verified_user.id, station_id=station.id)

    response = await client.delete(
        "/favorites",
        json={"station_id": str(station.id)},
        authenticate_with=verified_user,
    )

    assert response.status_code == 204

    favorites = await client.get("/favorites", authenticate_with=verified_user)
    assert favorites.json() == []


async def test_remove_favorite_not_favorited_returns_404(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(
        db, osm_id="node/1", name="Station 1", address="Addr 1"
    )

    response = await client.delete(
        "/favorites",
        json={"station_id": str(station.id)},
        authenticate_with=verified_user,
    )

    assert response.status_code == 404
