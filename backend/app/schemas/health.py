from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Application liveness status")
    app: str = Field(description="Configured neutral application name")
    environment: str = Field(description="Current deployment environment")
    version: str = Field(default="0.1.0", description="Application version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Server timestamp in UTC",
    )


class DatabaseReadiness(BaseModel):
    ready: bool = Field(description="Whether the PostgreSQL query succeeded")
    status: str = Field(description="Connection state: connected, disconnected, or error")
    database_name: str | None = Field(default=None, description="Active database catalog name")
    latency_ms: float = Field(description="Query execution latency in milliseconds")
    error: str | None = Field(default=None, description="Sanitized error description")


class ReadinessResponse(BaseModel):
    status: str = Field(description="Overall readiness state (ready or degraded)")
    database: DatabaseReadiness
    environment: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Server timestamp in UTC",
    )
