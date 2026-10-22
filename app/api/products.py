from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.repositories.mysql.products import MySQLProductRepository
from app.schemas.product import ProductCreate, ProductRead

router = APIRouter(prefix="/products", tags=["Products"])


@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
):
    repository = MySQLProductRepository(db)
    try:
        return repository.create(payload.model_dump())
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists.",
        )


@router.get("", response_model=list[ProductRead])
def list_products(
    category: str | None = None,
    color: str | None = None,
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    active_only: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if (
        min_price is not None
        and max_price is not None
        and min_price > max_price
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_price cannot exceed max_price.",
        )

    repository = MySQLProductRepository(db)
    return repository.search(
        category=category,
        color=color,
        min_price=min_price,
        max_price=max_price,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
):
    product = MySQLProductRepository(db).get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return product
