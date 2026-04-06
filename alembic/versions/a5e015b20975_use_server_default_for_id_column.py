"""Use server_default for id column

Revision ID: a5e015b20975
Revises: ac49b334803b
Create Date: 2026-04-06 13:20:25.820594

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5e015b20975"
down_revision: str | Sequence[str] | None = "ac49b334803b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

tables = ["user", "station", "price_registration"]


def upgrade() -> None:
    """Upgrade schema."""
    for table in tables:
        op.alter_column(
            table,
            "id",
            server_default=sa.text("gen_random_uuid()"),
        )


def downgrade() -> None:
    raise NotImplementedError
