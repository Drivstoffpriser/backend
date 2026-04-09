from uuid import uuid4

from app.core.db import DBSession
from app.stations.enums import FuelType
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory
from tests.users.factories import user_factory


async def test_get_user_price_registrations_requires_auth(
    client: AuthenticatedClient,
) -> None:
    response = await client.get("/users/price-registrations")

    assert response.status_code == 401


async def test_get_user_price_registrations_returns_zero_when_none(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db)

    response = await client.get("/users/price-registrations", authenticate_with=user)

    assert response.status_code == 200
    assert response.json() == {"total": 0}


async def test_get_user_price_registrations_returns_count(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db, firebase_uid=str(uuid4()), email="a@example.com")
    station = await station_factory(db)

    await price_update_factory(db, station_id=station.id, registered_by=user.id)
    await price_update_factory(
        db, station_id=station.id, registered_by=user.id, fuel_type=FuelType.GASOLINE_95
    )

    response = await client.get("/users/price-registrations", authenticate_with=user)

    assert response.status_code == 200
    assert response.json() == {"total": 2}


async def test_get_user_price_registrations_only_counts_own(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db, firebase_uid=str(uuid4()), email="b@example.com")
    other_user = await user_factory(
        db=db, firebase_uid=str(uuid4()), email="c@example.com"
    )
    station = await station_factory(db, external_id="node/999")

    await price_update_factory(db, station_id=station.id, registered_by=user.id)
    await price_update_factory(
        db,
        station_id=station.id,
        registered_by=other_user.id,
        fuel_type=FuelType.GASOLINE_95,
    )

    response = await client.get("/users/price-registrations", authenticate_with=user)

    assert response.status_code == 200
    assert response.json() == {"total": 1}
