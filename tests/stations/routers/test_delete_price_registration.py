from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.stations.models import PriceRegistration
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory


async def test_admin_deletes_latest_promotes_previous(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-price-1")
    older = await price_update_factory(
        db=db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime.now(UTC) - timedelta(days=2),
    )
    latest = await price_update_factory(
        db=db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("21.00"),
        registered_at=datetime.now(UTC),
    )

    response = await client.delete(
        f"/stations/{station.id}/prices/{latest.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 204
    remaining = await db.fetch_all(
        sa.select(PriceRegistration).where(
            PriceRegistration.station_id == station.id,
            PriceRegistration.fuel_type == FuelType.DIESEL,
        )
    )
    assert len(remaining) == 1
    assert remaining[0].id == older.id
    assert remaining[0].is_latest is True


async def test_admin_deletes_non_latest_leaves_latest_alone(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-price-2")
    older = await price_update_factory(
        db=db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        registered_at=datetime.now(UTC) - timedelta(days=2),
    )
    latest = await price_update_factory(
        db=db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        registered_at=datetime.now(UTC),
    )

    response = await client.delete(
        f"/stations/{station.id}/prices/{older.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 204
    row = await db.fetch_one(
        sa.select(PriceRegistration).where(PriceRegistration.id == latest.id)
    )
    assert row.is_latest is True


async def test_admin_deletes_only_registration_leaves_none_latest(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-price-3")
    only = await price_update_factory(
        db=db, station_id=station.id, fuel_type=FuelType.DIESEL
    )

    response = await client.delete(
        f"/stations/{station.id}/prices/{only.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 204
    remaining = await db.fetch_all(
        sa.select(PriceRegistration).where(PriceRegistration.station_id == station.id)
    )
    assert remaining == []


async def test_delete_price_rejects_non_admin(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-price-4")
    reg = await price_update_factory(db=db, station_id=station.id)

    response = await client.delete(
        f"/stations/{station.id}/prices/{reg.id}", authenticate_with=verified_user
    )

    assert response.status_code == 403


async def test_delete_price_rejects_unauthenticated(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/del-price-5")
    reg = await price_update_factory(db=db, station_id=station.id)

    response = await client.delete(f"/stations/{station.id}/prices/{reg.id}")

    assert response.status_code == 401


async def test_delete_price_returns_404_for_unknown_id(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station = await station_factory(db, external_id="node/del-price-6")

    response = await client.delete(
        f"/stations/{station.id}/prices/00000000-0000-0000-0000-000000000000",
        authenticate_with=admin_user,
    )

    assert response.status_code == 404


async def test_delete_price_returns_404_if_station_mismatch(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    station_a = await station_factory(db, external_id="node/del-price-7a")
    station_b = await station_factory(
        db, external_id="node/del-price-7b", lat=60.0, lng=11.0
    )
    reg = await price_update_factory(db=db, station_id=station_a.id)

    response = await client.delete(
        f"/stations/{station_b.id}/prices/{reg.id}",
        authenticate_with=admin_user,
    )

    assert response.status_code == 404
