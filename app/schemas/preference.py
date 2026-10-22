from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PreferenceWrite(BaseModel):
    style_preferences: dict = Field(default_factory=dict)
    preferred_colors: list[str] = Field(default_factory=list)
    sizes: dict[str, str] = Field(default_factory=dict)
    budget_min: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    budget_max: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )

    @model_validator(mode="after")
    def validate_budget(self):
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min cannot exceed budget_max")
        return self


class PreferenceRead(PreferenceWrite):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    updated_at: datetime
