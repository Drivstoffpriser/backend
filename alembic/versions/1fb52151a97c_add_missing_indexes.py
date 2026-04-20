"""add missing indexes

Revision ID: 1fb52151a97c
Revises: 5cbefe49984e
Create Date: 2026-04-20 21:37:32.362281

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1fb52151a97c"
down_revision: str | Sequence[str] | None = "5cbefe49984e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "idx_price_registration_registered_by",
        "price_registration",
        ["registered_by"],
    )
    op.create_index(
        "idx_station_updated_at",
        "station",
        [sa.literal_column("updated_at DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_station_updated_at", table_name="station")
    op.drop_index(
        "idx_price_registration_registered_by",
        table_name="price_registration",
    )
