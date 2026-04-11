from datetime import datetime

from app.core.db import DBSession
from tests.conftest import AuthenticatedClient
from tests.stations.factories import station_factory


async def test_get_last_updated_returns_null_when_no_stations(
    client: AuthenticatedClient,
) -> None:
    response = await client.get("/stations/last-updated")
    assert response.status_code == 200
    assert response.json()["lastUpdatedAt"] is None


async def test_get_last_updated_returns_latest_updated_at(
    client: AuthenticatedClient, db: DBSession
) -> None:
    s1 = await station_factory(
        db, external_id="node/1", name="Station 1", lat=59.911, lng=10.752
    )
    s2 = await station_factory(
        db, external_id="node/2", name="Station 2", lat=59.920, lng=10.760
    )

    response = await client.get("/stations/last-updated")
    assert response.status_code == 200

    last_updated_at = response.json()["lastUpdatedAt"]
    assert last_updated_at is not None

    later = max(s1.updated_at, s2.updated_at)
    assert datetime.fromisoformat(last_updated_at) == later
