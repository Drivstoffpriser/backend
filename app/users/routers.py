from typing import Annotated
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user as get_authenticated_user
from app.core.db import DBSession, get_db_session
from app.core.schemas import CamelCaseModel
from app.stations.models import PriceRegistration
from app.users.models import User

users_router = APIRouter(prefix="/users", tags=["users"])


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
