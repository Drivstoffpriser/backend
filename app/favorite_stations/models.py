from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FavoriteStation(Base):
    __tablename__ = "favorite_station"
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id", "station_id", name="uq_favorite_station_user_station"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(sa.ForeignKey("user.id"))
    station_id: Mapped[UUID] = mapped_column(sa.ForeignKey("station.id"))
