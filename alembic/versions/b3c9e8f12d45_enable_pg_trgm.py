"""enable pg_trgm

Revision ID: b3c9e8f12d45
Revises: 13d335342c43
Create Date: 2026-04-10 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c9e8f12d45"
down_revision: str | Sequence[str] | None = "13d335342c43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported.")
