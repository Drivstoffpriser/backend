from decimal import Decimal

import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.stations.models import PriceRegistration, Station
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory


async def test_delete_station_removes_station(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-1")

    response = await client.delete(
        f"/stations/{station.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 204
    row = await db.fetch_one_or_none(sa.select(Station).where(Station.id == station.id))
    assert row is None


async def test_delete_station_removes_price_registrations(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-2")
    await price_update_factory(
        db, station_id=station.id, fuel_type=FuelType.DIESEL, price=Decimal("20.00")
    )

    response = await client.delete(
        f"/stations/{station.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 204
    prices = await db.fetch_all(
        sa.select(PriceRegistration).where(PriceRegistration.station_id == station.id)
    )
    assert len(prices) == 0


async def test_delete_station_returns_404_for_unknown_id(
    client: AuthenticatedClient, admin_user: User
) -> None:
    response = await client.delete(
        "/stations/00000000-0000-0000-0000-000000000000",
        authenticate_with=admin_user,
    )

    assert response.status_code == 404


async def test_delete_station_rejects_non_admin(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-3")

    response = await client.delete(
        f"/stations/{station.id}",
        authenticate_with=verified_user,
    )

    assert response.status_code == 403


async def test_delete_station_rejects_unauthenticated(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/del-4")

    response = await client.delete(f"/stations/{station.id}")

    assert response.status_code == 401
