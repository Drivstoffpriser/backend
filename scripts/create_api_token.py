"""Create an API token for external data sharing.

Usage:
    uv run python scripts/create_api_token.py <service_name>

The plaintext token is printed once and never stored — save it immediately.
"""

import asyncio
import secrets
import sys

import sqlalchemy as sa

from app.core.db import Database
from app.external.auth import hash_token
from app.external.models import ApiToken


def generate_token() -> str:
    return f"dpp_{secrets.token_urlsafe(32)}"


async def main(service_name: str) -> None:
    plaintext = generate_token()
    token_hash = hash_token(plaintext)

    db = Database()
    async with db.session() as session:
        await session.execute(
            sa.insert(ApiToken).values(
                {
                    ApiToken.service_name: service_name,
                    ApiToken.token_hash: token_hash,
                }
            )
        )

    print(f"Token created for '{service_name}':")
    print(f"  {plaintext}")
    print()
    print("Save this token now — it cannot be retrieved later.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <name>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
