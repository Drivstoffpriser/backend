"""add on delete constraints to price_registration and favorite_station

Revision ID: 018b998ca8a1
Revises: 4d5d7e759be5
Create Date: 2026-04-13 13:47:25.462349

"""

from collections.abc import Sequence

import alembic.op as op

# revision identifiers, used by Alembic.
revision: str = "018b998ca8a1"
down_revision: str | Sequence[str] | None = "4d5d7e759be5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "price_registration_registered_by_fkey",
        "price_registration",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "price_registration_registered_by_fkey",
        "price_registration",
        "user",
        ["registered_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "favorite_station_user_id_fkey", "favorite_station", type_="foreignkey"
    )
    op.create_foreign_key(
        "favorite_station_user_id_fkey",
        "favorite_station",
        "user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "favorite_station_station_id_fkey", "favorite_station", type_="foreignkey"
    )
    op.create_foreign_key(
        "favorite_station_station_id_fkey",
        "favorite_station",
        "station",
        ["station_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "price_registration_registered_by_fkey",
        "price_registration",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "price_registration_registered_by_fkey",
        "price_registration",
        "user",
        ["registered_by"],
        ["id"],
    )

    op.drop_constraint(
        "favorite_station_user_id_fkey", "favorite_station", type_="foreignkey"
    )
    op.create_foreign_key(
        "favorite_station_user_id_fkey",
        "favorite_station",
        "user",
        ["user_id"],
        ["id"],
    )

    op.drop_constraint(
        "favorite_station_station_id_fkey", "favorite_station", type_="foreignkey"
    )
    op.create_foreign_key(
        "favorite_station_station_id_fkey",
        "favorite_station",
        "station",
        ["station_id"],
        ["id"],
    )
