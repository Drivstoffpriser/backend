from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    __tablename__ = "user"

    firebase_uid: Mapped[str] = mapped_column(sa.String, unique=True)
    email: Mapped[str | None] = mapped_column(sa.String, unique=True)
    display_name: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    is_admin: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.text("false"))
