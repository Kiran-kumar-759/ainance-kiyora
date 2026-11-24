import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_email_verified: bool
    onboarding_completed: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserUpdateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)


class UserPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preferred_currency: str = "INR"
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"
    date_format: str = "DD/MM/YYYY"
    notification_preferences: dict[str, Any] = Field(default_factory=dict)


class UserPreferenceUpdateRequest(BaseModel):
    preferred_currency: str | None = Field(None, max_length=10)
    locale: str | None = Field(None, max_length=20)
    timezone: str | None = Field(None, max_length=50)
    date_format: str | None = Field(None, max_length=20)
    notification_preferences: dict[str, Any] | None = None
