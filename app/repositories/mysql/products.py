from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.product import Product


class MySQLProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def create(self, data: dict) -> Product:
        product = Product(**data)
        self.db.add(product)
        try:
            self.db.commit()
            self.db.refresh(product)
            return product
        except IntegrityError:
            self.db.rollback()
            raise

    def search(
        self,
        category: str | None = None,
        color: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        active_only: bool = True,
        in_stock_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Product]:
        statement = select(Product)

        if active_only:
            statement = statement.where(Product.is_active.is_(True))
        if in_stock_only:
            statement = statement.where(Product.stock > 0)
        if category:
            statement = statement.where(Product.category == category)
        if min_price is not None:
            statement = statement.where(Product.price >= min_price)
        if max_price is not None:
            statement = statement.where(Product.price <= max_price)
        if color:
            statement = statement.where(
                Product.attributes["color"].as_string() == color
            )

        statement = statement.order_by(Product.id.desc())
        statement = statement.offset(offset).limit(limit)
        return list(self.db.scalars(statement).all())
