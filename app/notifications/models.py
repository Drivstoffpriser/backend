from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.notifications.enums import Platform
from app.stations.enums import FuelType


class UserFcmToken(Base):
    __tablename__ = "user_fcm_token"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String, unique=True)
    platform: Mapped[Platform] = mapped_column(
        sa.Enum(Platform, length=50, native_enum=False)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now()
    )


class PriceAlert(Base):
    __tablename__ = "price_alert"
    __table_args__ = (
        sa.UniqueConstraint(
            "user_id",
            "station_id",
            "fuel_type",
            name="uq_price_alert_user_station_fuel",
        ),
        sa.Index(
            "uq_price_alert_user_fuel_no_station",
            "user_id",
            "fuel_type",
            unique=True,
            postgresql_where=sa.text("station_id IS NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    station_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("station.id", ondelete="CASCADE"), nullable=True
    )
    fuel_type: Mapped[FuelType] = mapped_column(
        sa.Enum(FuelType, length=50, native_enum=False)
    )
    threshold_price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
