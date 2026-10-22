import pytest
from pydantic import ValidationError

from app.schemas.chat_intent import ChatIntent


def test_general_intent_accepts_no_filters():
    result = ChatIntent(intent="general", action="general")

    assert result.intent == "general"
    assert result.action == "general"
    assert result.category is None
    assert result.color is None
    assert result.clear_filters == []


def test_product_search_accepts_filters():
    result = ChatIntent.model_validate({
        "intent": "product_search",
        "action": "new_search",
        "category": "T-Shirts",
        "color": "black",
        "min_price": 10,
        "max_price": 30,
    })

    assert result.intent == "product_search"
    assert result.action == "new_search"
    assert result.category == "T-Shirts"
    assert result.color == "black"
    assert result.min_price == 10
    assert result.max_price == 30


def test_modify_filters_accepts_partial_update():
    result = ChatIntent(
        intent="product_search",
        action="modify_filters",
        color="white",
    )

    assert result.color == "white"
    assert result.category is None
    assert result.max_price is None


def test_modify_filters_can_clear_budget():
    result = ChatIntent(
        intent="product_search",
        action="modify_filters",
        clear_filters=["max_price"],
    )

    assert result.clear_filters == ["max_price"]


def test_min_price_cannot_exceed_max_price():
    with pytest.raises(ValidationError):
        ChatIntent.model_validate({
            "intent": "product_search",
            "action": "new_search",
            "min_price": 50,
            "max_price": 20,
        })


def test_general_intent_rejects_search_filters():
    with pytest.raises(ValidationError):
        ChatIntent.model_validate({
            "intent": "general",
            "action": "general",
            "color": "black",
        })


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        ChatIntent.model_validate({
            "intent": "general",
            "action": "general",
            "unexpected": "value",
        })


def test_negative_price_is_rejected():
    with pytest.raises(ValidationError):
        ChatIntent.model_validate({
            "intent": "product_search",
            "action": "new_search",
            "min_price": -1,
        })


def test_cannot_set_and_clear_same_filter():
    with pytest.raises(ValidationError):
        ChatIntent(
            intent="product_search",
            action="modify_filters",
            color="white",
            clear_filters=["color"],
        )


def test_product_search_cannot_use_general_action():
    with pytest.raises(ValidationError):
        ChatIntent(
            intent="product_search",
            action="general",
        )


def test_clarification_accepts_conflicting_price_request():
    intent = ChatIntent(
        intent="product_search",
        action="new_search",
        needs_clarification=True,
        clarification_reason="conflicting_price_constraints",
    )
    assert intent.needs_clarification is True
    assert intent.clarification_reason == "conflicting_price_constraints"


def test_clarification_requires_reason():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatIntent(
            intent="product_search",
            action="new_search",
            needs_clarification=True,
        )


def test_clarification_rejects_price_values():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatIntent(
            intent="product_search",
            action="new_search",
            min_price=50,
            needs_clarification=True,
            clarification_reason="conflicting_price_constraints",
        )


def test_clarification_rejects_general_intent():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ChatIntent(
            intent="general",
            action="general",
            needs_clarification=True,
            clarification_reason="conflicting_price_constraints",
        )
