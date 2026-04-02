"""initial

Revision ID: e34b89f7b41a
Revises:
Create Date: 2026-03-27 21:58:56.730987

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e34b89f7b41a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported.")
