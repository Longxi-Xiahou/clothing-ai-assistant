from decimal import Decimal
from typing import Protocol

from app.models.product import Product
from app.models.user import User
from app.models.preference import UserPreference


class ProductRepository(Protocol):
    def get_by_id(self, product_id: int) -> Product | None: ...
    def create(self, data: dict) -> Product: ...
    def search(
        self,
        category: str | None = None,
        color: str | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        active_only: bool = True,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Product]: ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: int) -> User | None: ...
    def create(self, data: dict) -> User: ...


class PreferenceRepository(Protocol):
    def get_by_user_id(self, user_id: int) -> UserPreference | None: ...
    def save(self, user_id: int, data: dict) -> UserPreference: ...
