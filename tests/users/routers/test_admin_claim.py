from collections.abc import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import firebase_admin.auth  # type: ignore[import-untyped]
import pytest
import sqlalchemy as sa

from app.core.db import DBSession
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.users.factories import user_factory, verified_user_factory


@pytest.fixture
def mock_set_claims() -> Generator[MagicMock]:
    with patch("app.users.routers.firebase_admin.auth.set_custom_user_claims") as mock:
        yield mock


async def test_promote_sets_claim_and_db_flag(
    client: AuthenticatedClient,
    db: DBSession,
    admin_user: User,
    mock_set_claims: MagicMock,
) -> None:
    target = await verified_user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )

    response = await client.post(
        f"/users/{target.id}/admin", authenticate_with=admin_user
    )

    assert response.status_code == 204
    mock_set_claims.assert_called_once()
    args, _ = mock_set_claims.call_args
    assert args[0] == "target-uid"
    assert args[1] == {"admin": True}

    row = await db.fetch_one(sa.select(User).where(User.id == target.id))
    assert row.is_admin is True


async def test_demote_clears_claim_and_db_flag(
    client: AuthenticatedClient,
    db: DBSession,
    admin_user: User,
    mock_set_claims: MagicMock,
) -> None:
    target = await verified_user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )
    await db.execute(
        sa.update(User).where(User.id == target.id).values({User.is_admin: True})
    )
    await db.commit()

    response = await client.delete(
        f"/users/{target.id}/admin", authenticate_with=admin_user
    )

    assert response.status_code == 204
    args, _ = mock_set_claims.call_args
    assert args[1] == {"admin": False}

    row = await db.fetch_one(sa.select(User).where(User.id == target.id))
    assert row.is_admin is False


async def test_promote_rejects_non_admin(
    client: AuthenticatedClient,
    db: DBSession,
    verified_user: User,
    mock_set_claims: MagicMock,
) -> None:
    target = await user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )

    response = await client.post(
        f"/users/{target.id}/admin", authenticate_with=verified_user
    )

    assert response.status_code == 403
    mock_set_claims.assert_not_called()


async def test_promote_rejects_unauthenticated(
    client: AuthenticatedClient, db: DBSession, mock_set_claims: MagicMock
) -> None:
    target = await user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )

    response = await client.post(f"/users/{target.id}/admin")

    assert response.status_code == 401
    mock_set_claims.assert_not_called()


async def test_promote_returns_404_for_unknown_id(
    client: AuthenticatedClient,
    admin_user: User,
    mock_set_claims: MagicMock,
) -> None:
    response = await client.post(
        f"/users/{uuid4()}/admin", authenticate_with=admin_user
    )

    assert response.status_code == 404
    mock_set_claims.assert_not_called()


async def test_promote_returns_404_when_firebase_user_missing(
    client: AuthenticatedClient,
    db: DBSession,
    admin_user: User,
    mock_set_claims: MagicMock,
) -> None:
    target = await verified_user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )
    mock_set_claims.side_effect = firebase_admin.auth.UserNotFoundError("not found")

    response = await client.post(
        f"/users/{target.id}/admin", authenticate_with=admin_user
    )

    assert response.status_code == 404
    row = await db.fetch_one(sa.select(User).where(User.id == target.id))
    assert row.is_admin is False


async def test_demote_rejects_self(
    client: AuthenticatedClient,
    admin_user: User,
    mock_set_claims: MagicMock,
) -> None:
    response = await client.delete(
        f"/users/{admin_user.id}/admin", authenticate_with=admin_user
    )

    assert response.status_code == 400
    mock_set_claims.assert_not_called()


async def test_get_user_by_email_returns_user(
    client: AuthenticatedClient, db: DBSession, admin_user: User
) -> None:
    target = await verified_user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )

    response = await client.get(
        "/users/by-email",
        params={"email": target.email},
        authenticate_with=admin_user,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(target.id)
    assert data["email"] == "target@example.com"


async def test_get_user_by_email_rejects_non_admin(
    client: AuthenticatedClient, db: DBSession, verified_user: User
) -> None:
    target = await verified_user_factory(
        db=db, firebase_uid="target-uid", email="target@example.com"
    )

    response = await client.get(
        "/users/by-email",
        params={"email": target.email},
        authenticate_with=verified_user,
    )

    assert response.status_code == 403


async def test_get_user_by_email_returns_404_for_unknown_email(
    client: AuthenticatedClient, admin_user: User
) -> None:
    response = await client.get(
        "/users/by-email",
        params={"email": "nobody@example.com"},
        authenticate_with=admin_user,
    )

    assert response.status_code == 404
