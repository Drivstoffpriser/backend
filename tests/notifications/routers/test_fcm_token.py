import sqlalchemy as sa

from app.core.db import DBSession
from app.notifications.enums import Platform
from app.notifications.models import UserFcmToken
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.notifications.factories import fcm_token_factory


async def test_register_fcm_token(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    response = await client.post(
        "/notifications/fcm-token",
        json={"token": "abc123", "platform": "IOS"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 204
    token = await db.fetch_one_or_none(
        sa.select(UserFcmToken).where(UserFcmToken.token == "abc123")
    )
    assert token is not None
    assert token.user_id == unverified_user.id
    assert token.platform == Platform.IOS


async def test_register_fcm_token_is_idempotent(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await client.post(
        "/notifications/fcm-token",
        json={"token": "abc123", "platform": "IOS"},
        authenticate_with=unverified_user,
    )
    response = await client.post(
        "/notifications/fcm-token",
        json={"token": "abc123", "platform": "ANDROID"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 204
    rows = await db.fetch_all(
        sa.select(UserFcmToken).where(UserFcmToken.token == "abc123")
    )
    assert len(rows) == 1
    assert rows[0].platform == Platform.ANDROID


async def test_unregister_fcm_token(
    client: AuthenticatedClient, db: DBSession, unverified_user: User
) -> None:
    await fcm_token_factory(db, user_id=unverified_user.id, token="abc123")

    response = await client.delete(
        "/notifications/fcm-token",
        json={"token": "abc123"},
        authenticate_with=unverified_user,
    )

    assert response.status_code == 204
    token = await db.fetch_one_or_none(
        sa.select(UserFcmToken).where(UserFcmToken.token == "abc123")
    )
    assert token is None


async def test_unregister_nonexistent_token_is_noop(
    client: AuthenticatedClient, unverified_user: User
) -> None:
    response = await client.delete(
        "/notifications/fcm-token",
        json={"token": "does-not-exist"},
        authenticate_with=unverified_user,
    )
    assert response.status_code == 204
