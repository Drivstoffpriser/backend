import asyncio
import contextlib
from typing import Annotated
from uuid import UUID

import firebase_admin.auth  # type: ignore[import-untyped]
import sqlalchemy as sa
from fastapi import APIRouter, Depends
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate

from app.core.auth import get_current_user as get_authenticated_user
from app.core.auth import get_firebase_app
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel
from app.stations.models import PriceRegistration
from app.users.models import User

users_router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[
        Depends(RateLimiter(limiter=Limiter(Rate(10, Duration.SECOND * 10))))
    ],
)


class GetCurrentUserResponseBody(CamelCaseModel):
    id: UUID
    firebase_uid: str
    email: str | None
    display_name: str | None
    is_admin: bool


@users_router.get("/me")
async def get_current_user(
    current_user: Annotated[User, Depends(get_authenticated_user)],
) -> GetCurrentUserResponseBody:
    return GetCurrentUserResponseBody(
        id=current_user.id,
        firebase_uid=current_user.firebase_uid,
        email=current_user.email,
        display_name=current_user.display_name,
        is_admin=current_user.is_admin,
    )


@users_router.delete("/me", status_code=204)
async def delete_current_user(
    current_user: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> None:
    # Delete user from Firebase. If not found, delete user from our db
    with contextlib.suppress(firebase_admin.auth.UserNotFoundError):
        await asyncio.to_thread(
            firebase_admin.auth.delete_user,
            current_user.firebase_uid,
            app=get_firebase_app(),
        )

    await db.execute(sa.delete(User).where(User.id == current_user.id))
    await db.commit()


class GetUserPriceRegistrationsResponseBody(CamelCaseModel):
    total: int


@users_router.get("/price-registrations")
async def get_user_price_registrations(
    current_user: Annotated[User, Depends(get_authenticated_user)],
    db: Annotated[DBSession, Depends(get_db_session)],
) -> GetUserPriceRegistrationsResponseBody:
    total = await db.fetch_one(
        sa.select(sa.func.count()).where(
            PriceRegistration.registered_by == current_user.id
        )
    )
    return GetUserPriceRegistrationsResponseBody(total=total)
