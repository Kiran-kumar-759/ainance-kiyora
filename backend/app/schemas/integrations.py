import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

IntegrationCategory = Literal[
    "banking",
    "email",
    "sms",
    "ai",
    "web_research",
    "notifications",
]

IntegrationStatus = Literal[
    "connected",
    "available",
    "configured_not_connected",
    "unavailable",
    "error",
    "planned",
]


class IntegrationItemResponse(BaseModel):
    provider_id: str
    name: str
    category: IntegrationCategory
    description: str
    status: IntegrationStatus
    configured: bool
    connected: bool
    available: bool
    is_planned: bool = False
    is_preferred: bool = False
    can_test: bool = False
    can_connect: bool = False
    can_disconnect: bool = False
    capabilities: list[str] = Field(default_factory=list)
    required_env_vars: list[str] = Field(default_factory=list)
    last_sync_or_test_at: dt.datetime | None = None
    last_error: str | None = None
    safe_metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationConnectionSummary(BaseModel):
    connection_id: uuid.UUID
    connection_type: Literal["banking", "email"]
    provider_id: str
    display_name: str
    status: str
    account_or_email: str | None = None
    linked_accounts_count: int = 0
    scopes: list[str] = Field(default_factory=list)
    token_expires_at: dt.datetime | None = None
    last_sync_at: dt.datetime | None = None
    last_error: str | None = None
    can_disconnect: bool = True


class IntegrationsOverviewResponse(BaseModel):
    total_integrations: int
    configured_count: int
    connected_count: int
    unavailable_count: int
    attention_required_count: int
    planned_count: int
    preferred_web_provider: str
    web_search_enabled: bool
    integrations: list[IntegrationItemResponse]
    connections: list[IntegrationConnectionSummary]


class IntegrationTestResponse(BaseModel):
    provider_id: str
    status: Literal["ok", "unavailable", "error", "rate_limited", "timeout"]
    success: bool
    message: str
    latency_ms: int | None = None
    checked_at: dt.datetime
    details: dict[str, Any] = Field(default_factory=dict)


class IntegrationDisconnectResponse(BaseModel):
    connection_id: uuid.UUID
    connection_type: Literal["banking", "email"]
    status: str
    message: str
