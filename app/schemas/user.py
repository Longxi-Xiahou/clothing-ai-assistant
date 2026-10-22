from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    external_id: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None
    display_name: str | None
    created_at: datetime
