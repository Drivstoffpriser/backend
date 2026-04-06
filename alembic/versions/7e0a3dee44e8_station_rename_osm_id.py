"""Station: Rename osm_id

Revision ID: 7e0a3dee44e8
Revises: a5e015b20975
Create Date: 2026-04-06 14:38:25.846521

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e0a3dee44e8"
down_revision: str | Sequence[str] | None = "a5e015b20975"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("station", "osm_id", new_column_name="external_id")


def downgrade() -> None:
    raise NotImplementedError
