from datetime import UTC, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.stations.models import PriceRegistration
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory
from tests.users.factories import verified_user_factory


async def test_contributors_empty_database(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await verified_user_factory(db=db)
    response = await client.get("/statistics/contributors", authenticate_with=user)

    assert response.status_code == 200
    data = response.json()
    assert data["last24Hours"] == []
    assert data["total"] == []


async def test_contributors_total_ranking(
    client: AuthenticatedClient, db: DBSession
) -> None:
    top_user = await verified_user_factory(
        db=db, firebase_uid="top", email="top@example.com", display_name="Top User"
    )
    other_user = await verified_user_factory(
        db=db,
        firebase_uid="other",
        email="other@example.com",
        display_name="Other User",
    )
    station = await station_factory(db=db, external_id="node/1", lng=10.1)
    station2 = await station_factory(db=db, external_id="node/2", lng=10.2)
    station3 = await station_factory(db=db, external_id="node/3", lng=10.3)

    # top_user: 2 registrations, other_user: 1
    await price_update_factory(
        db, station_id=station.id, registered_by=top_user.id, fuel_type=FuelType.DIESEL
    )
    await price_update_factory(
        db,
        station_id=station2.id,
        registered_by=top_user.id,
        fuel_type=FuelType.DIESEL,
    )
    await price_update_factory(
        db,
        station_id=station3.id,
        registered_by=other_user.id,
        fuel_type=FuelType.DIESEL,
    )

    response = await client.get("/statistics/contributors", authenticate_with=top_user)

    assert response.status_code == 200
    total = response.json()["total"]
    assert len(total) == 2
    assert total[0]["displayName"] == "Top User"
    assert total[0]["count"] == 2
    assert total[1]["displayName"] == "Other User"
    assert total[1]["count"] == 1


async def test_contributors_24h_filter(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await verified_user_factory(
        db=db, firebase_uid="u1", email="u1@example.com", display_name="Active User"
    )
    station = await station_factory(db=db, external_id="node/1", lng=10.1)
    station2 = await station_factory(db=db, external_id="node/2", lng=10.2)
    now = datetime.now(UTC)

    await price_update_factory(
        db,
        station_id=station.id,
        registered_by=user.id,
        fuel_type=FuelType.DIESEL,
        registered_at=now - timedelta(hours=1),
    )
    await price_update_factory(
        db,
        station_id=station2.id,
        registered_by=user.id,
        fuel_type=FuelType.GASOLINE_95,
        registered_at=now - timedelta(days=5),
    )

    response = await client.get("/statistics/contributors", authenticate_with=user)

    assert response.status_code == 200
    data = response.json()
    assert data["last24Hours"][0]["displayName"] == "Active User"
    assert data["last24Hours"][0]["count"] == 1
    assert data["total"][0]["count"] == 2


async def test_contributors_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.get("/statistics/contributors")
    assert response.status_code == 401


async def test_contributors_excludes_anonymous_registrations(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await verified_user_factory(db=db)
    station = await station_factory(db=db, external_id="node/1", lng=10.1)

    # Insert a registration with no user
    await db.execute(
        sa.insert(PriceRegistration).values(
            {
                PriceRegistration.station_id: station.id,
                PriceRegistration.fuel_type: FuelType.DIESEL,
                PriceRegistration.price: Decimal("20.00"),
                PriceRegistration.registered_by: None,
                PriceRegistration.is_latest: True,
            }
        )
    )

    response = await client.get("/statistics/contributors", authenticate_with=user)

    assert response.status_code == 200
    assert response.json()["total"] == []
    assert response.json()["last24Hours"] == []
