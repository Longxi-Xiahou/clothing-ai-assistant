import pytest

from app.services.intent_classifier import _parse_json_object


def test_parse_plain_json():
    result = _parse_json_object(
        '{"intent":"product_search","category":"T-Shirts","color":"black"}'
    )

    assert result["intent"] == "product_search"
    assert result["category"] == "T-Shirts"
    assert result["color"] == "black"


def test_parse_json_after_think_section():
    content = (
        '<think>Internal reasoning text</think>\n'
        '{"intent":"general","category":null,"color":null}'
    )

    result = _parse_json_object(content)

    assert result["intent"] == "general"


def test_parse_json_with_leading_text():
    content = (
        'Some leading text\n'
        '{"intent":"general","category":null,"color":null}'
    )

    result = _parse_json_object(content)

    assert result["intent"] == "general"


def test_invalid_json_raises_value_error():
    with pytest.raises(ValueError):
        _parse_json_object('{"intent": "general"')


def test_missing_json_object_raises_value_error():
    with pytest.raises(ValueError):
        _parse_json_object("No JSON was returned")


def test_non_object_json_is_rejected():
    with pytest.raises(ValueError):
        _parse_json_object('[{"intent":"general"}]')


def test_conflicting_price_bounds_become_clarification():
    from app.services.intent_classifier import _normalize_price_conflict

    parsed = {
        "intent": "product_search",
        "action": "new_search",
        "category": "Hoodies",
        "color": None,
        "min_price": 50,
        "max_price": 30,
        "clear_filters": [],
        "needs_clarification": False,
        "clarification_reason": None,
    }

    result = _normalize_price_conflict(parsed)

    assert result["min_price"] is None
    assert result["max_price"] is None
    assert result["needs_clarification"] is True
    assert result["clarification_reason"] == "conflicting_price_constraints"
    assert result["category"] == "Hoodies"


def test_valid_price_bounds_are_unchanged():
    from app.services.intent_classifier import _normalize_price_conflict

    parsed = {
        "intent": "product_search",
        "action": "new_search",
        "min_price": 20,
        "max_price": 50,
        "clear_filters": [],
        "needs_clarification": False,
        "clarification_reason": None,
    }

    result = _normalize_price_conflict(parsed)

    assert result["min_price"] == 20
    assert result["max_price"] == 50
    assert result["needs_clarification"] is False
