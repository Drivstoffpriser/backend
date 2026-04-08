from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.db import DBSession
from app.stations.enums import FuelType
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.stations.factories import price_update_factory, station_factory


async def test_get_price_history_empty(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    history = response.json()["history"]
    assert history == {ft.value: [] for ft in FuelType}


async def test_get_price_history_single_price(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=datetime.now(UTC),
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history[FuelType.DIESEL]) == 1
    assert history[FuelType.DIESEL][0]["averagePrice"] == "20.00"
    assert history[FuelType.GASOLINE_95] == []
    assert history[FuelType.GASOLINE_98] == []


async def test_get_price_history_averages_same_day(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    today = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=today,
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("22.00"),
        registered_at=today.replace(hour=18),
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    diesel_history = response.json()["history"][FuelType.DIESEL]
    assert len(diesel_history) == 1
    assert diesel_history[0]["averagePrice"] == "21.00"


async def test_get_price_history_separate_days_ordered(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    now = datetime.now(UTC)
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("21.00"),
        registered_at=now - timedelta(days=2),
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(days=1),
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    diesel_history = response.json()["history"][FuelType.DIESEL]
    assert len(diesel_history) == 2
    # oldest first
    assert diesel_history[0]["averagePrice"] == "21.00"
    assert diesel_history[1]["averagePrice"] == "20.00"


async def test_get_price_history_separate_fuel_types(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    now = datetime.now(UTC)
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now,
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("25.00"),
        registered_at=now,
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    history = response.json()["history"]
    assert len(history[FuelType.DIESEL]) == 1
    assert history[FuelType.DIESEL][0]["averagePrice"] == "20.00"
    assert len(history[FuelType.GASOLINE_95]) == 1
    assert history[FuelType.GASOLINE_95][0]["averagePrice"] == "25.00"
    assert history[FuelType.GASOLINE_98] == []


async def test_get_price_history_excludes_older_than_30_days(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    now = datetime.now(UTC)
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("18.00"),
        registered_at=now - timedelta(days=31),
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now,
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    diesel_history = response.json()["history"][FuelType.DIESEL]
    assert len(diesel_history) == 1
    assert diesel_history[0]["averagePrice"] == "20.00"


async def test_get_price_history_returns_recent_updates(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    now = datetime.now(UTC)
    for i in range(12):
        await price_update_factory(
            db,
            station_id=station.id,
            fuel_type=FuelType.DIESEL,
            price=Decimal("20.00"),
            registered_at=now - timedelta(days=i),
        )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    recent_updates = response.json()["recentUpdates"]
    assert len(recent_updates) == 10
    # most recent first
    assert recent_updates[0]["registeredAt"] > recent_updates[1]["registeredAt"]


async def test_get_price_history_recent_updates_across_fuel_types(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db, external_id="node/1")
    now = datetime.now(UTC)
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.DIESEL,
        price=Decimal("20.00"),
        registered_at=now - timedelta(hours=1),
    )
    await price_update_factory(
        db,
        station_id=station.id,
        fuel_type=FuelType.GASOLINE_95,
        price=Decimal("25.00"),
        registered_at=now,
    )

    response = await client.get(
        f"/stations/{station.id}/history",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 200
    recent_updates = response.json()["recentUpdates"]
    assert len(recent_updates) == 2
    assert recent_updates[0]["fuelType"] == FuelType.GASOLINE_95
    assert recent_updates[1]["fuelType"] == FuelType.DIESEL


async def test_get_price_history_requires_auth(
    client: AuthenticatedClient, db: DBSession
) -> None:
    station = await station_factory(db, external_id="node/1")

    response = await client.get(f"/stations/{station.id}/history")

    assert response.status_code == 401
