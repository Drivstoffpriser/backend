from app.core.db import DBSession
from tests.conftest import AuthenticatedClient
from tests.users.factories import user_factory


async def test_get_current_user_returns_current_user(
    client: AuthenticatedClient, db: DBSession
) -> None:
    user = await user_factory(db=db)

    response = await client.get("/users/me", authenticate_with=user)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user.id)
    assert data["firebaseUid"] == user.firebase_uid
    assert data["email"] == user.email
    assert data["displayName"] == user.display_name
    assert data["isAdmin"] == user.is_admin


async def test_get_current_user_requires_auth(client: AuthenticatedClient) -> None:
    response = await client.get("/users/me")

    assert response.status_code == 401
