from datetime import UTC, datetime
from typing import cast

import sqlalchemy as sa

from app.core.db import DBSession
from app.users.models import User


async def user_factory(
    *,
    db: DBSession,
    firebase_uid: str = "test-uid",
    email: str | None = "test@example.com",
    display_name: str | None = "Test User",
    verified_at: datetime | None = None,
) -> User:
    result = await db.execute(
        sa.insert(User)
        .values(
            {
                User.firebase_uid: firebase_uid,
                User.email: email,
                User.display_name: display_name,
                User.verified_at: verified_at,
            }
        )
        .returning(User)
    )
    return cast(User, result.scalars().one())


async def verified_user_factory(
    *,
    db: DBSession,
    firebase_uid: str = "test-uid",
    email: str | None = "test@example.com",
    display_name: str | None = "Test User",
) -> User:
    return await user_factory(
        db=db,
        firebase_uid=firebase_uid,
        email=email,
        display_name=display_name,
        verified_at=datetime.now(UTC),
    )


async def admin_user_factory(
    *,
    db: DBSession,
    firebase_uid: str = "admin-uid",
    email: str | None = "admin@example.com",
    display_name: str | None = "Admin User",
) -> User:
    user = await verified_user_factory(
        db=db,
        firebase_uid=firebase_uid,
        email=email,
        display_name=display_name,
    )
    result = await db.execute(
        sa.update(User)
        .where(User.id == user.id)
        .values({User.is_admin: True})
        .returning(User)
    )
    return cast(User, result.scalars().one())
