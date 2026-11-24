from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserPreferenceResponse


class OnboardingStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    onboarding_completed: bool
    is_email_verified: bool
    full_name: str
    preferences: UserPreferenceResponse


class OnboardingUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=100)
    preferred_currency: str | None = Field(None, max_length=10)
    locale: str | None = Field(None, max_length=20)
    timezone: str | None = Field(None, max_length=50)
    date_format: str | None = Field(None, max_length=20)
    notification_preferences: dict[str, Any] | None = None
