import asyncio
import contextlib
from typing import Annotated
from uuid import UUID

import firebase_admin.auth
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate

from app.core.auth import get_admin_user, get_firebase_app
from app.core.auth import get_current_user as get_authenticated_user
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


async def _set_admin_claim(firebase_uid: str, is_admin: bool) -> None:
    try:
        await asyncio.to_thread(
            firebase_admin.auth.set_custom_user_claims,
            firebase_uid,
            {"admin": is_admin},
            app=get_firebase_app(),
        )
    except firebase_admin.auth.UserNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in Firebase",
        ) from e


async def _update_admin(
    *,
    user_id: UUID,
    is_admin: bool,
    db: DBSession,
) -> None:
    user = await db.fetch_one_or_none(sa.select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    await _set_admin_claim(user.firebase_uid, is_admin)

    await db.execute(
        sa.update(User).where(User.id == user_id).values({User.is_admin: is_admin})
    )
    await db.commit()


class UserLookupResponseBody(CamelCaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    is_admin: bool


@users_router.get("/by-email")
async def get_user_by_email(
    email: str,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_admin_user)],
) -> UserLookupResponseBody:
    user = await db.fetch_one_or_none(sa.select(User).where(User.email == email))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return UserLookupResponseBody(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
    )


@users_router.post("/{user_id}/admin", status_code=204)
async def promote_admin(
    user_id: UUID,
    db: Annotated[DBSession, Depends(get_db_session)],
    _: Annotated[User, Depends(get_admin_user)],
) -> None:
    await _update_admin(user_id=user_id, is_admin=True, db=db)


@users_router.delete("/{user_id}/admin", status_code=204)
async def demote_admin(
    user_id: UUID,
    db: Annotated[DBSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_admin_user)],
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote yourself",
        )
    await _update_admin(user_id=user_id, is_admin=False, db=db)
