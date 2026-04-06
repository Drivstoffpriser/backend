from typing import cast
from uuid import uuid4

import sqlalchemy as sa

from app.core.db import DBSession
from app.external.auth import hash_token
from app.external.models import ApiToken


async def api_token_factory(
    *,
    db: DBSession,
    service_name: str = "test-consumer",
    plaintext: str | None = None,
    is_active: bool = True,
) -> tuple[ApiToken, str]:

    if plaintext is None:
        plaintext = f"dpp_test_{uuid4().hex}"
    token_hash = hash_token(plaintext)

    result = await db.execute(
        sa.insert(ApiToken)
        .values(
            {
                ApiToken.service_name: service_name,
                ApiToken.token_hash: token_hash,
                ApiToken.is_active: is_active,
            }
        )
        .returning(ApiToken)
    )

    return cast(ApiToken, result.scalar_one()), plaintext
