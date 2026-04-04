from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user as get_authenticated_user
from app.core.schemas import CamelCaseModel
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
