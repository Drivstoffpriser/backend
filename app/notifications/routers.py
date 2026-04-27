from decimal import Decimal
from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.auth import get_current_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel
from app.notifications.enums import Platform
from app.notifications.models import PriceAlert, UserFcmToken
from app.stations.enums import FuelType
from app.users.models import User

notifications_router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[
        Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 10))))
    ],
)


class PostRegisterFcmTokenRequestBody(CamelCaseModel):
    token: str
    platform: Platform


@notifications_router.post("/fcm-token", status_code=204)
async def register_fcm_token(
    body: PostRegisterFcmTokenRequestBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    await db.execute(
        pg_insert(UserFcmToken)
        .values(
            {
                UserFcmToken.user_id: current_user.id,
                UserFcmToken.token: body.token,
                UserFcmToken.platform: body.platform,
                UserFcmToken.updated_at: sa.func.now(),
            }
        )
        .on_conflict_do_update(
            index_elements=[UserFcmToken.token],
            set_={
                UserFcmToken.user_id: current_user.id,
                UserFcmToken.platform: body.platform,
                UserFcmToken.updated_at: sa.func.now(),
            },
        )
    )
    await db.commit()


class DeleteFcmTokenRequestBody(CamelCaseModel):
    token: str


@notifications_router.delete("/fcm-token", status_code=204)
async def unregister_fcm_token(
    body: DeleteFcmTokenRequestBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    await db.execute(
        sa.delete(UserFcmToken).where(
            UserFcmToken.user_id == current_user.id,
            UserFcmToken.token == body.token,
        )
    )
    await db.commit()


class AlertSchema(CamelCaseModel):
    id: UUID
    station_id: UUID | None
    fuel_type: FuelType
    threshold_price: Decimal


class GetAlertsResponseBody(CamelCaseModel):
    alerts: list[AlertSchema]


@notifications_router.get("/alerts")
async def get_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> GetAlertsResponseBody:
    alerts = await db.fetch_all(
        sa.select(PriceAlert).where(PriceAlert.user_id == current_user.id)
    )
    return GetAlertsResponseBody(
        alerts=[
            AlertSchema(
                id=a.id,
                station_id=a.station_id,
                fuel_type=a.fuel_type,
                threshold_price=a.threshold_price,
            )
            for a in alerts
        ]
    )


class PostAlertRequestBody(CamelCaseModel):
    station_id: UUID | None = None
    fuel_type: FuelType
    threshold_price: Decimal


@notifications_router.post("/alerts", status_code=201)
async def create_alert(
    body: PostAlertRequestBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> AlertSchema:
    stmt = pg_insert(PriceAlert).values(
        {
            PriceAlert.user_id: current_user.id,
            PriceAlert.station_id: body.station_id,
            PriceAlert.fuel_type: body.fuel_type,
            PriceAlert.threshold_price: body.threshold_price,
        }
    )
    upsert_set = {
        PriceAlert.threshold_price: body.threshold_price,
        PriceAlert.last_notified_at: None,
    }
    if body.station_id is not None:
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_alert_user_station_fuel",
            set_=upsert_set,
        )
    else:
        stmt = stmt.on_conflict_do_update(
            index_elements=[PriceAlert.user_id, PriceAlert.fuel_type],
            index_where=PriceAlert.station_id.is_(None),
            set_=upsert_set,
        )
    result = await db.execute(stmt.returning(PriceAlert))
    alert = result.scalar_one()
    await db.commit()
    return AlertSchema(
        id=alert.id,
        station_id=alert.station_id,
        fuel_type=alert.fuel_type,
        threshold_price=alert.threshold_price,
    )


class PatchUpdateAlertRequestBody(CamelCaseModel):
    threshold_price: Decimal


@notifications_router.patch("/alerts/{alert_id}", status_code=204)
async def update_alert(
    alert_id: UUID,
    body: PatchUpdateAlertRequestBody,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    result = await db.execute(
        sa.update(PriceAlert)
        .where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == current_user.id,
        )
        .values({PriceAlert.threshold_price: body.threshold_price})
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    await db.commit()


@notifications_router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    result = await db.execute(
        sa.delete(PriceAlert).where(
            PriceAlert.id == alert_id,
            PriceAlert.user_id == current_user.id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    await db.commit()
