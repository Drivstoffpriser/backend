import sqlalchemy as sa
from geoalchemy2 import Geography, WKBElement
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.stations.enums import ProviderType


class Station(Base):
    __tablename__ = "station"
    __table_args__ = (
        sa.UniqueConstraint("address", "city", name="uq_station_address_city"),
        sa.Index(
            "uq_station_location", sa.text("ST_AsText(location::geometry)"), unique=True
        ),
    )

    osm_id: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    provider: Mapped[ProviderType] = mapped_column(
        sa.Enum(ProviderType, length=50, native_enum=False)
    )
    address: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    location: Mapped[WKBElement] = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=False)
    )
