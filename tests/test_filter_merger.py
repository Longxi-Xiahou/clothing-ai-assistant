from decimal import Decimal

from app.schemas.chat_intent import ChatIntent
from app.services.filter_merger import merge_filters


def test_modify_color_preserves_category_and_budget():
    previous = {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": Decimal("30"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="modify_filters",
        color="white",
    )

    result = merge_filters(previous, intent)

    assert result == {
        "category": "T-Shirts",
        "color": "white",
        "min_price": None,
        "max_price": Decimal("30"),
    }


def test_modify_budget_preserves_other_filters():
    previous = {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": Decimal("30"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="modify_filters",
        max_price=20,
    )

    result = merge_filters(previous, intent)

    assert result["category"] == "T-Shirts"
    assert result["color"] == "black"
    assert result["max_price"] == 20


def test_new_search_replaces_old_filters():
    previous = {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": Decimal("30"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="new_search",
        category="Jeans",
        color="blue",
    )

    result = merge_filters(previous, intent)

    assert result == {
        "category": "Jeans",
        "color": "blue",
        "min_price": None,
        "max_price": None,
    }


def test_clear_budget_preserves_category_and_color():
    previous = {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": Decimal("30"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="modify_filters",
        clear_filters=["max_price"],
    )

    result = merge_filters(previous, intent)

    assert result["category"] == "T-Shirts"
    assert result["color"] == "black"
    assert result["max_price"] is None


def test_general_intent_clears_search_filters():
    previous = {
        "category": "T-Shirts",
        "color": "black",
        "min_price": None,
        "max_price": Decimal("30"),
    }
    intent = ChatIntent(intent="general", action="general")

    result = merge_filters(previous, intent)

    assert all(value is None for value in result.values())


def test_clear_color_and_update_budget():
    previous = {
        "category": "Jeans",
        "color": "blue",
        "min_price": None,
        "max_price": Decimal("100"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="modify_filters",
        max_price=50,
        clear_filters=["color"],
    )

    result = merge_filters(previous, intent)

    assert result == {
        "category": "Jeans",
        "color": None,
        "min_price": None,
        "max_price": 50,
    }


def test_merge_rejects_conflicting_price_range():
    previous = {
        "category": "T-Shirts",
        "color": None,
        "min_price": Decimal("40"),
        "max_price": Decimal("60"),
    }
    intent = ChatIntent(
        intent="product_search",
        action="modify_filters",
        max_price=30,
    )

    import pytest

    with pytest.raises(ValueError, match="Merged min_price cannot exceed max_price"):
        merge_filters(previous, intent)
