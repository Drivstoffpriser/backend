import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.enums import ProviderType
from app.stations.models import Station
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import station_factory


async def test_update_station_changes_name(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/upd-1")

    response = await client.patch(
        f"/stations/{station.id}",
        json={"name": "Updated Name"},
        authenticate_with=admin_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"

    row = await db.fetch_one(sa.select(Station).where(Station.id == station.id))
    assert row.name == "Updated Name"


async def test_update_station_changes_provider(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(
        db, external_id="node/upd-2", provider=ProviderType.CIRCLE_K
    )

    response = await client.patch(
        f"/stations/{station.id}",
        json={"provider": ProviderType.UNO_X},
        authenticate_with=admin_user,
    )

    assert response.status_code == 200
    row = await db.fetch_one(sa.select(Station).where(Station.id == station.id))
    assert row.provider == ProviderType.UNO_X


async def test_update_station_changes_location(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/upd-3")

    response = await client.patch(
        f"/stations/{station.id}",
        json={"location": {"lat": 60.0, "lng": 11.0}},
        authenticate_with=admin_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert abs(data["location"]["lat"] - 60.0) < 0.001
    assert abs(data["location"]["lng"] - 11.0) < 0.001


async def test_update_station_partial_update_preserves_other_fields(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(
        db, external_id="node/upd-4", name="Original Name", city="Bergen"
    )

    response = await client.patch(
        f"/stations/{station.id}",
        json={"city": "Stavanger"},
        authenticate_with=admin_user,
    )

    assert response.status_code == 200
    row = await db.fetch_one(sa.select(Station).where(Station.id == station.id))
    assert row.name == "Original Name"
    assert row.city == "Stavanger"


async def test_update_station_returns_404_for_unknown_id(
    client: AuthenticatedClient, admin_user: User
) -> None:
    response = await client.patch(
        "/stations/00000000-0000-0000-0000-000000000000",
        json={"name": "New Name"},
        authenticate_with=admin_user,
    )

    assert response.status_code == 404


async def test_update_station_rejects_non_admin(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(db, external_id="node/upd-5")

    response = await client.patch(
        f"/stations/{station.id}",
        json={"name": "Hacked"},
        authenticate_with=verified_user,
    )

    assert response.status_code == 403


async def test_update_station_rejects_unauthenticated(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/upd-6")

    response = await client.patch(
        f"/stations/{station.id}",
        json={"name": "Hacked"},
    )

    assert response.status_code == 401
