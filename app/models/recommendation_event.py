from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 6), nullable=True
    )
    feedback: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
