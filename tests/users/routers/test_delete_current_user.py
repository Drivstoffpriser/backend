from collections.abc import Generator
from unittest.mock import MagicMock, patch
from uuid import uuid4

import firebase_admin.auth  # type: ignore[import-untyped]
import pytest
import sqlalchemy as sa

import app.users.routers
from app.core.db import DBSession
from app.favorite_stations.models import FavoriteStation
from app.stations.models import PriceRegistration
from app.users.models import User
from tests.conftest import AuthenticatedClient
from tests.favorite_stations.factories import favorite_station_factory
from tests.stations.factories import price_update_factory, station_factory
from tests.users.factories import user_factory


@pytest.fixture(autouse=True)
def mock_firebase_delete() -> Generator[MagicMock]:
    with (
        patch.object(app.users.routers, "get_firebase_app", return_value=MagicMock()),
        patch.object(firebase_admin.auth, "delete_user") as mock_delete,
    ):
        yield mock_delete


async def test_delete_current_user(client: AuthenticatedClient, db: DBSession) -> None:
    user = await user_factory(db=db)

    response = await client.delete("/users/me", authenticate_with=user)

    assert response.status_code == 204
    assert await db.fetch_one_or_none(sa.select(User).where(User.id == user.id)) is None


async def test_delete_current_user_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.delete("/users/me")

    assert response.status_code == 401


async def test_delete_current_user_cascades_favorite_stations(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db)
    station = await station_factory(db)
    await favorite_station_factory(db, user_id=user.id, station_id=station.id)

    await client.delete("/users/me", authenticate_with=user)

    favorites = await db.fetch_all(
        sa.select(FavoriteStation).where(FavoriteStation.user_id == user.id)
    )
    assert favorites == []


async def test_delete_current_user_nullifies_price_registrations(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db, firebase_uid=str(uuid4()), email="a@example.com")
    station = await station_factory(db)
    registration = await price_update_factory(
        db, station_id=station.id, registered_by=user.id
    )

    await client.delete("/users/me", authenticate_with=user)

    result = await db.execute(
        sa.select(PriceRegistration.registered_by).where(
            PriceRegistration.id == registration.id
        )
    )
    assert result.scalar_one() is None


async def test_delete_current_user_deletes_if_not_found_in_firebase(
    client: AuthenticatedClient,
    db: DBSession,
    mock_firebase_delete: MagicMock,
) -> None:
    user = await user_factory(db=db)
    mock_firebase_delete.side_effect = firebase_admin.auth.UserNotFoundError(
        "not found"
    )

    response = await client.delete("/users/me", authenticate_with=user)

    assert response.status_code == 204
    assert await db.fetch_one_or_none(sa.select(User).where(User.id == user.id)) is None


async def test_delete_current_user_aborts_on_firebase_error(
    client: AuthenticatedClient,
    db: DBSession,
    mock_firebase_delete: MagicMock,
) -> None:
    user = await user_factory(db=db)
    mock_firebase_delete.side_effect = Exception("Firebase error")

    with pytest.raises(Exception, match="Firebase error"):
        await client.delete("/users/me", authenticate_with=user)

    assert (
        await db.fetch_one_or_none(sa.select(User).where(User.id == user.id))
        is not None
    )
