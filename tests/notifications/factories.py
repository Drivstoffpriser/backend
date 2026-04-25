from decimal import Decimal
from typing import cast
from uuid import UUID

import sqlalchemy as sa

from app.core.db import DBSession
from app.notifications.enums import Platform
from app.notifications.models import PriceAlert, UserFcmToken
from app.stations.enums import FuelType


async def fcm_token_factory(
    db: DBSession,
    *,
    user_id: UUID,
    token: str = "test-fcm-token",
    platform: Platform = Platform.ANDROID,
) -> UserFcmToken:
    result = await db.execute(
        sa.insert(UserFcmToken)
        .values(
            {
                UserFcmToken.user_id: user_id,
                UserFcmToken.token: token,
                UserFcmToken.platform: platform,
                UserFcmToken.updated_at: sa.func.now(),
            }
        )
        .returning(UserFcmToken)
    )
    return cast(UserFcmToken, result.scalar_one())


async def price_alert_factory(
    db: DBSession,
    *,
    user_id: UUID,
    station_id: UUID | None = None,
    fuel_type: FuelType = FuelType.DIESEL,
    threshold_price: Decimal = Decimal("20.00"),
) -> PriceAlert:
    result = await db.execute(
        sa.insert(PriceAlert)
        .values(
            {
                PriceAlert.user_id: user_id,
                PriceAlert.station_id: station_id,
                PriceAlert.fuel_type: fuel_type,
                PriceAlert.threshold_price: threshold_price,
            }
        )
        .returning(PriceAlert)
    )
    return cast(PriceAlert, result.scalar_one())
