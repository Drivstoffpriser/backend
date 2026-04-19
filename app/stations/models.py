from datetime import datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from geoalchemy2 import Geography, WKBElement
from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.stations.enums import FuelType, PriceRegistrationSourceType, ProviderType


class Station(Base):
    __tablename__ = "station"
    __table_args__ = (
        sa.UniqueConstraint("address", "city", name="uq_station_address_city"),
        sa.Index("idx_station_location", "location", postgresql_using="gist"),
        sa.Index(
            "uq_station_location", sa.text("ST_AsText(location::geometry)"), unique=True
        ),
    )

    external_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    provider: Mapped[ProviderType] = mapped_column(
        sa.Enum(ProviderType, length=50, native_enum=False)
    )
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now()
    )


class PriceRegistration(Base):
    __tablename__ = "price_registration"
    __table_args__ = (
        sa.Index(
            "uq_price_registration_latest_per_station_fuel",
            "station_id",
            "fuel_type",
            unique=True,
            postgresql_where=sa.text("is_latest = true"),
        ),
    )

    station_id: Mapped[UUID] = mapped_column(
        ForeignKey("station.id", ondelete="CASCADE")
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa.func.now()
    )
    fuel_type: Mapped[FuelType] = mapped_column(
        sa.Enum(FuelType, length=50, native_enum=False)
    )
    price: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2))
    source_type: Mapped[PriceRegistrationSourceType] = mapped_column(
        sa.Enum(PriceRegistrationSourceType, length=50, native_enum=False),
        server_default=PriceRegistrationSourceType.USER,
    )
    # Set to null if user deletes their account, or if imported from an external source
    registered_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL")
    )
    is_latest: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"))
