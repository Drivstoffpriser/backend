from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import firebase_admin.auth  # type: ignore[import-untyped]
import pytest
from fastapi.security import HTTPAuthorizationCredentials

import app.core.auth
from app.core.auth import get_current_user
from app.core.db import DBSession
from tests.users.factories import user_factory


def _make_credentials() -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")


def _patch_firebase(decoded: dict[str, Any]) -> Any:
    return patch.object(
        firebase_admin.auth,
        "verify_id_token",
        return_value=decoded,
    )


@pytest.fixture(autouse=True)
def patch_firebase_app() -> Generator[None]:
    with patch.object(app.core.auth, "get_firebase_app", return_value=MagicMock()):
        yield


async def test_new_verified_user_is_created(db: DBSession) -> None:
    decoded = {
        "uid": "new-uid",
        "email": "new@example.com",
        "name": "New User",
        "email_verified": True,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.firebase_uid == "new-uid"
    assert user.email == "new@example.com"
    assert user.display_name == "New User"
    assert user.verified_at is not None


async def test_new_unverified_user_is_created(db: DBSession) -> None:
    decoded = {
        "uid": "new-uid",
        "email": "new@example.com",
        "email_verified": False,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.firebase_uid == "new-uid"
    assert user.email == "new@example.com"
    assert user.verified_at is None


async def test_existing_user_is_returned(db: DBSession) -> None:
    existing = await user_factory(db=db, firebase_uid="existing-uid")
    decoded = {
        "uid": "existing-uid",
        "email": existing.email,
        "name": existing.display_name,
        "email_verified": True,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.id == existing.id


async def test_verified_at_set_when_existing_user_has_email_and_no_verified_at(
    db: DBSession,
) -> None:
    existing = await user_factory(
        db=db, firebase_uid="uid-unverified", email="v@example.com", verified_at=None
    )
    assert existing.verified_at is None

    decoded = {
        "uid": "uid-unverified",
        "email": "v@example.com",
        "email_verified": True,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.verified_at is not None


async def test_verified_at_not_overwritten_when_already_set(db: DBSession) -> None:
    original_ts = datetime(2025, 1, 1, tzinfo=UTC)
    await user_factory(
        db=db,
        firebase_uid="uid-already-verified",
        email="already@example.com",
        verified_at=original_ts,
    )

    decoded = {
        "uid": "uid-already-verified",
        "email": "already@example.com",
        "email_verified": True,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.verified_at == original_ts


async def test_verified_at_not_set_when_email_not_verified(db: DBSession) -> None:
    existing = await user_factory(
        db=db,
        firebase_uid="uid-unverified-email",
        email="unv@example.com",
        verified_at=None,
    )

    decoded = {
        "uid": "uid-unverified-email",
        "email": "unv@example.com",
        "email_verified": False,
    }

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.id == existing.id
    assert user.verified_at is None


async def test_anonymous_user_has_no_verified_at(db: DBSession) -> None:
    decoded = {"uid": "anon-uid", "provider_id": "anonymous"}

    with _patch_firebase(decoded):
        user = await get_current_user(db=db, credentials=_make_credentials())

    assert user.firebase_uid == "anon-uid"
    assert user.email is None
    assert user.verified_at is None
