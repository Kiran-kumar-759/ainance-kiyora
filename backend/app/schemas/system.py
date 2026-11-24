from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SystemSettingBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingResponse(SystemSettingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PlatformInfoResponse(BaseModel):
    app_name: str
    version: str
    phase: str
    target_market: str
    primary_currency: str
    fiscal_year_cycle: str
    environment: str
    database_connected: bool
    database_name: str | None = None
    settings_count: int
    timestamp: datetime
