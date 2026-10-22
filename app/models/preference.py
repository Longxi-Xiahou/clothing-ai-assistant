from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    style_preferences: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False
    )
    preferred_colors: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    sizes: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False
    )
    budget_min: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    budget_max: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        nullable=False
    )
