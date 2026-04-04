import asyncio
import base64
import json
from functools import lru_cache
from typing import Annotated, cast

import firebase_admin  # type: ignore[import-untyped]
import firebase_admin.auth  # type: ignore[import-untyped]
import firebase_admin.credentials  # type: ignore[import-untyped]
import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.db import DBSession, get_db_session
from app.users.models import User

_bearer = HTTPBearer()


@lru_cache(maxsize=1)
def _get_firebase_app() -> firebase_admin.App:
    settings = get_settings()
    if settings.firebase_service_account_b64:
        cred = firebase_admin.credentials.Certificate(
            json.loads(base64.b64decode(settings.firebase_service_account_b64))
        )
    else:
        cred = firebase_admin.credentials.ApplicationDefault()
    return firebase_admin.initialize_app(cred)


async def get_current_user(
    db: Annotated[DBSession, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> User:
    try:
        decoded = await asyncio.to_thread(
            firebase_admin.auth.verify_id_token,
            credentials.credentials,
            app=_get_firebase_app(),
        )
    except firebase_admin.auth.ExpiredIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from e
    except (firebase_admin.auth.InvalidIdTokenError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from e

    uid: str = decoded["uid"]
    email: str | None = decoded.get("email")
    display_name: str | None = decoded.get("name")

    result = await db.execute(
        pg_insert(User)
        .values(
            {
                User.firebase_uid: uid,
                User.email: email,
                User.display_name: display_name,
            }
        )
        .on_conflict_do_nothing(index_elements=[User.firebase_uid])
        .returning(User)
    )
    user: User | None = result.scalars().one_or_none()
    if user is not None:
        return user

    existing: User = await db.fetch_one(sa.select(User).where(User.firebase_uid == uid))
    if existing.verified_at is None and email is not None:
        result = await db.execute(
            sa.update(User)
            .where(User.firebase_uid == uid)
            .values({User.verified_at: sa.func.now()})
            .returning(User)
        )
        return cast(User, result.scalars().one())
    return existing


async def get_verified_user(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified"
        )
    return user
