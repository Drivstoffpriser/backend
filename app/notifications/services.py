"""FCM push notification service for price drop alerts."""

import asyncio
from decimal import Decimal
from uuid import UUID

import firebase_admin.messaging
import sqlalchemy as sa

from app.core.auth import get_firebase_app
from app.core.db import DBSession, db
from app.core.logging import logger
from app.favorite_stations.models import FavoriteStation
from app.notifications.models import PriceAlert, UserFcmToken
from app.stations.constants import FUEL_TYPE_NORWEGIAN
from app.stations.enums import FuelType
from app.stations.models import Station

_COOLDOWN = sa.text("interval '1 day'")


def _not_on_cooldown() -> sa.ColumnElement[bool]:
    return sa.or_(
        PriceAlert.last_notified_at.is_(None),
        PriceAlert.last_notified_at < sa.func.now() - _COOLDOWN,
    )


async def send_price_drop_notifications(
    *,
    db: DBSession,
    station_id: UUID,
    fuel_type: FuelType,
    new_price: Decimal,
) -> None:
    """Send FCM push notifications to users whose alert threshold is met.

    Only fires if the new price is at or below the user's threshold and the
    alert has not been triggered within the last day.
    """
    station_alerts = await db.fetch_all(
        sa.select(PriceAlert).where(
            PriceAlert.station_id == station_id,
            PriceAlert.fuel_type == fuel_type,
            PriceAlert.threshold_price >= new_price,
            _not_on_cooldown(),
        )
    )
    favorites_alerts = await db.fetch_all(
        sa.select(PriceAlert)
        .join(
            FavoriteStation,
            sa.and_(
                FavoriteStation.user_id == PriceAlert.user_id,
                FavoriteStation.station_id == station_id,
            ),
        )
        .where(
            PriceAlert.station_id.is_(None),
            PriceAlert.fuel_type == fuel_type,
            PriceAlert.threshold_price >= new_price,
            _not_on_cooldown(),
        )
    )
    alerts = [*station_alerts, *favorites_alerts]
    if not alerts:
        return

    alert_ids = [a.id for a in alerts]
    user_ids = [a.user_id for a in alerts]

    station = await db.fetch_one_or_none(
        sa.select(Station).where(Station.id == station_id)
    )
    station_name = station.name if station else "Ukjent stasjon"

    tokens = await db.fetch_all(
        sa.select(UserFcmToken).where(UserFcmToken.user_id.in_(user_ids))
    )
    if not tokens:
        return

    token_strings = [row.token for row in tokens]
    token_id_by_token = {row.token: row.id for row in tokens}

    message = firebase_admin.messaging.MulticastMessage(
        tokens=token_strings,
        notification=firebase_admin.messaging.Notification(
            title="Prisvarsel",
            body=f"{station_name}: {FUEL_TYPE_NORWEGIAN[fuel_type]} "
            f"koster nå {new_price:.2f} kr",
        ),
        data={
            "station_id": str(station_id),
            "fuel_type": str(fuel_type),
            "price": str(new_price),
        },
    )

    try:
        response = await asyncio.to_thread(
            firebase_admin.messaging.send_each_for_multicast,
            message,
            app=get_firebase_app(),
        )
    except Exception:
        logger.exception("Failed to send FCM notifications for station %s", station_id)
        return

    stale_token_ids = [
        token_id_by_token[token_strings[i]]
        for i, r in enumerate(response.responses)
        if not r.success
        and r.exception is not None
        and "unregistered" in str(r.exception).lower()
    ]
    if stale_token_ids:
        await db.execute(
            sa.delete(UserFcmToken).where(UserFcmToken.id.in_(stale_token_ids))
        )

    await db.execute(
        sa.update(PriceAlert)
        .where(PriceAlert.id.in_(alert_ids))
        .values({PriceAlert.last_notified_at: sa.func.now()})
    )
    await db.commit()

    logger.info(
        "Sent %d/%d FCM notifications for %s %s @ %.2f kr (%s)",
        response.success_count,
        len(token_strings),
        fuel_type,
        station_name,
        new_price,
        station_id,
    )


async def send_price_drop_notifications_background(
    *,
    station_id: UUID,
    fuel_type: FuelType,
    new_price: Decimal,
) -> None:
    async with db.session() as session:
        await send_price_drop_notifications(
            db=session,
            station_id=station_id,
            fuel_type=fuel_type,
            new_price=new_price,
        )
