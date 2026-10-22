from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


FilterName = Literal["category", "color", "min_price", "max_price"]
ClarificationReason = Literal["conflicting_price_constraints"]


class ChatIntent(BaseModel):
    """Validated intent, filter changes, and clarification state."""

    model_config = ConfigDict(extra="forbid")

    intent: Literal["general", "product_search"]
    action: Literal["new_search", "modify_filters", "general"]

    category: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=50)

    min_price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    max_price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )

    clear_filters: list[FilterName] = Field(default_factory=list)

    needs_clarification: bool = False
    clarification_reason: ClarificationReason | None = None

    @model_validator(mode="after")
    def validate_intent_and_filters(self):
        if self.needs_clarification:
            if self.intent != "product_search":
                raise ValueError(
                    "Clarification requires product_search intent"
                )

            if self.clarification_reason is None:
                raise ValueError(
                    "Clarification requires a clarification_reason"
                )

            if self.min_price is not None or self.max_price is not None:
                raise ValueError(
                    "Price fields must be null when clarification is needed"
                )

            if self.clear_filters:
                raise ValueError(
                    "Cannot clear filters while clarification is pending"
                )

        elif self.clarification_reason is not None:
            raise ValueError(
                "clarification_reason requires needs_clarification=true"
            )

        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price cannot exceed max_price")

        if self.intent == "general":
            if self.action != "general":
                raise ValueError("General intent requires action='general'")

            if any(
                value is not None
                for value in (
                    self.category,
                    self.color,
                    self.min_price,
                    self.max_price,
                )
            ) or self.clear_filters:
                raise ValueError(
                    "General intent cannot include product-search filters"
                )

            if self.needs_clarification:
                raise ValueError(
                    "General intent cannot require clarification"
                )

        elif self.action == "general":
            raise ValueError(
                "Product-search intent cannot use action='general'"
            )

        if len(self.clear_filters) != len(set(self.clear_filters)):
            raise ValueError("clear_filters cannot contain duplicates")

        for field_name in self.clear_filters:
            if getattr(self, field_name) is not None:
                raise ValueError(
                    f"{field_name} cannot have a value and be cleared at once"
                )

        return self
