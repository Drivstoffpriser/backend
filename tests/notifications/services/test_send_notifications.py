from decimal import Decimal
from unittest.mock import MagicMock, patch

import firebase_admin.messaging

import app.core.auth as core_auth
from app.core.db import DBSession
from app.notifications.services import send_price_drop_notifications
from app.stations.enums import FuelType
from app.users.models import User
from tests.favorite_stations.factories import favorite_station_factory
from tests.notifications.factories import fcm_token_factory, price_alert_factory
from tests.stations.factories import station_factory


def _mock_fcm_response(*, success_count: int = 1) -> MagicMock:
    response = MagicMock()
    response.success_count = success_count
    response.responses = [MagicMock(success=True) for _ in range(success_count)]
    return response


async def test_favorites_alert_fires_for_favorited_station(
    db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    await favorite_station_factory(
        db, user_id=unverified_user.id, station_id=station.id
    )
    await price_alert_factory(
        db, user_id=unverified_user.id, threshold_price=Decimal("20.00")
    )
    await fcm_token_factory(db, user_id=unverified_user.id)

    with (
        patch.object(
            firebase_admin.messaging,
            "send_each_for_multicast",
            return_value=_mock_fcm_response(),
        ) as mock_send,
        patch.object(core_auth, "get_firebase_app", return_value=MagicMock()),
    ):
        await send_price_drop_notifications(
            db=db,
            station_id=station.id,
            fuel_type=FuelType.DIESEL,
            new_price=Decimal("19.99"),
        )

    mock_send.assert_called_once()


async def test_favorites_alert_does_not_fire_for_non_favorited_station(
    db: DBSession, unverified_user: User
) -> None:
    station = await station_factory(db)
    # No favorite_station record — user has NOT favorited this station
    await price_alert_factory(
        db, user_id=unverified_user.id, threshold_price=Decimal("20.00")
    )
    await fcm_token_factory(db, user_id=unverified_user.id)

    with patch.object(firebase_admin.messaging, "send_each_for_multicast") as mock_send:
        await send_price_drop_notifications(
            db=db,
            station_id=station.id,
            fuel_type=FuelType.DIESEL,
            new_price=Decimal("19.99"),
        )

    mock_send.assert_not_called()
