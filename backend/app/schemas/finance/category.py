import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CategoryType = Literal["income", "expense"]


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category_type: CategoryType = Field(...)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=30)


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=30)


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    name: str
    category_type: str
    icon: str | None = None
    color: str | None = None
    is_system: bool
    created_at: dt.datetime
