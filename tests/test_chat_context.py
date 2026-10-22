from types import SimpleNamespace

from app.api.chat import _build_product_context


def test_empty_products_return_no_match_message():
    result = _build_product_context([])

    assert "No matching products" in result
    assert "Do not recommend or invent" in result


def test_product_context_includes_database_fields():
    product = SimpleNamespace(
        id=1,
        sku="TSHIRT-001",
        name="Basic Cotton T-Shirt",
        category="T-Shirts",
        brand="Demo Brand",
        price="24.99",
        currency="USD",
        stock=50,
        attributes={
            "color": "black",
            "sizes": ["S", "M", "L"],
        },
        description="Everyday cotton T-shirt",
    )

    result = _build_product_context([product])

    assert "Basic Cotton T-Shirt" in result
    assert "TSHIRT-001" in result
    assert "T-Shirts" in result
    assert "24.99 USD" in result
    assert "Stock: 50" in result
    assert "'color': 'black'" in result
