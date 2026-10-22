from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    stock: int = Field(default=0, ge=0)
    attributes: dict = Field(default_factory=dict)
    image_url: str | None = Field(default=None, max_length=1024)
    is_active: bool = True


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    category: str | None
    brand: str | None
    price: Decimal
    currency: str
    stock: int
    attributes: dict
    image_url: str | None
    is_active: bool
