import hashlib
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.db import DBSession, get_db_session
from app.external.models import ApiToken

_bearer = HTTPBearer()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def get_api_token(
    db: Annotated[DBSession, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> ApiToken:
    token_hash = hash_token(credentials.credentials)
    api_token = await db.fetch_one_or_none(
        sa.select(ApiToken).where(
            ApiToken.token_hash == token_hash,
            ApiToken.is_active.is_(True),
        )
    )
    if api_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token"
        )

    return api_token
