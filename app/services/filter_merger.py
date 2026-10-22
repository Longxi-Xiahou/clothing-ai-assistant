from decimal import Decimal
from typing import Any

from app.schemas.chat_intent import ChatIntent


FILTER_FIELDS = ("category", "color", "min_price", "max_price")


def merge_filters(
    previous_filters: dict[str, Any] | None,
    intent: ChatIntent,
) -> dict[str, Any]:
    """Merge validated filter changes with previously saved filters."""

    previous = previous_filters or {}

    if intent.intent == "general" or intent.action == "new_search":
        merged = {field: None for field in FILTER_FIELDS}
    else:
        merged = {
            field: previous.get(field)
            for field in FILTER_FIELDS
        }

    for field in intent.clear_filters:
        merged[field] = None

    for field in FILTER_FIELDS:
        value = getattr(intent, field)
        if value is not None:
            merged[field] = value

    min_price = merged["min_price"]
    max_price = merged["max_price"]

    if min_price is not None and max_price is not None:
        if Decimal(str(min_price)) > Decimal(str(max_price)):
            raise ValueError("Merged min_price cannot exceed max_price")

    return merged
