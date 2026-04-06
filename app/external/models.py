import sqlalchemy as sa
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ApiToken(Base):
    __tablename__ = "api_token"

    service_name: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("true"))

    __table_args__ = (
        sa.Index(
            "uq_api_token_active_service_name",
            "service_name",
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        ),
    )
