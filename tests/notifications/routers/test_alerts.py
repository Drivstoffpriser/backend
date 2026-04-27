from decimal import Decimal

import sqlalchemy as sa

from app.core.db import DBSession
from app.notifications.models import PriceAlert
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.notifications.factories import price_alert_factory
from tests.stations.factories import station_factory


async def test_create_alert(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)

    response = await client.post(
        "/notifications/alerts",
        json={
            "stationId": str(station.id),
            "fuelType": "DIESEL",
            "thresholdPrice": "19.99",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["stationId"] == str(station.id)
    assert body["fuelType"] == "DIESEL"
    assert Decimal(body["thresholdPrice"]) == Decimal("19.99")


async def test_create_alert_upserts_on_duplicate(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    await price_alert_factory(
        db,
        user_id=unverified_user.id,
        station_id=station.id,
        threshold_price=Decimal("20.00"),
    )

    response = await client.post(
        "/notifications/alerts",
        json={
            "stationId": str(station.id),
            "fuelType": "DIESEL",
            "thresholdPrice": "18.00",
        },
        authenticate_with=unverified_user,
    )

    assert response.status_code == 201
    rows = await db.fetch_all(
        sa.select(PriceAlert).where(PriceAlert.user_id == unverified_user.id)
    )
    assert len(rows) == 1
    assert rows[0].threshold_price == Decimal("18.00")


async def test_get_alerts(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    await price_alert_factory(db, user_id=unverified_user.id, station_id=station.id)

    response = await client.get(
        "/notifications/alerts", authenticate_with=unverified_user
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["stationId"] == str(station.id)


async def test_patch_alert(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    alert = await price_alert_factory(
        db,
        user_id=unverified_user.id,
        station_id=station.id,
        threshold_price=Decimal("20.00"),
    )

    response = await client.patch(
        f"/notifications/alerts/{alert.id}",
        json={"thresholdPrice": "17.50"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 204


async def test_patch_alert_not_found(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    from uuid import uuid4

    response = await client.patch(
        f"/notifications/alerts/{uuid4()}",
        json={"thresholdPrice": "17.50"},
        authenticate_with=unverified_user,
    )
    assert response.status_code == 404


async def test_delete_alert(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    alert = await price_alert_factory(
        db, user_id=unverified_user.id, station_id=station.id
    )

    response = await client.delete(
        f"/notifications/alerts/{alert.id}",
        authenticate_with=unverified_user,
    )

    assert response.status_code == 204
    row = await db.fetch_one_or_none(
        sa.select(PriceAlert).where(PriceAlert.id == alert.id)
    )
    assert row is None


async def test_delete_alert_not_found(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    from uuid import uuid4

    response = await client.delete(
        f"/notifications/alerts/{uuid4()}",
        authenticate_with=unverified_user,
    )
    assert response.status_code == 404


async def test_create_favorites_alert(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    response = await client.post(
        "/notifications/alerts",
        json={"fuelType": "DIESEL", "thresholdPrice": "19.99"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["stationId"] is None
    assert body["fuelType"] == "DIESEL"
    assert Decimal(body["thresholdPrice"]) == Decimal("19.99")


async def test_create_favorites_alert_upserts_on_duplicate(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await price_alert_factory(
        db,
        user_id=unverified_user.id,
        threshold_price=Decimal("20.00"),
    )

    response = await client.post(
        "/notifications/alerts",
        json={"fuelType": "DIESEL", "thresholdPrice": "18.00"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 201
    rows = await db.fetch_all(
        sa.select(PriceAlert).where(PriceAlert.user_id == unverified_user.id)
    )
    assert len(rows) == 1
    assert rows[0].threshold_price == Decimal("18.00")


async def test_get_alerts_includes_favorites_alert(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await price_alert_factory(db, user_id=unverified_user.id)

    response = await client.get(
        "/notifications/alerts", authenticate_with=unverified_user
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["stationId"] is None


async def test_cannot_access_other_users_alert(
    client: AuthenticatedClient,
    db: DBSession,
    unverified_user: User,
    verified_user: User,
) -> None:
    station = await station_factory(db)
    alert = await price_alert_factory(
        db, user_id=verified_user.id, station_id=station.id
    )

    response = await client.delete(
        f"/notifications/alerts/{alert.id}",
        authenticate_with=unverified_user,
    )
    assert response.status_code == 404
