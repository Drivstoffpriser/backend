"""add station timestamps

Revision ID: 4d5d7e759be5
Revises: b3c9e8f12d45
Create Date: 2026-04-11 10:44:48.044316

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4d5d7e759be5"
down_revision: str | Sequence[str] | None = "b3c9e8f12d45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "station",
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "station",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported.")
