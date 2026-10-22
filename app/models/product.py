from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, Integer, JSON, Numeric, String, Text, func
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(
        String(100), index=True, nullable=True
    )
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), default="USD", nullable=False
    )
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attributes: Mapped[dict] = mapped_column(
        JSON, default=dict, nullable=False
    )
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(),
        nullable=False
    )
