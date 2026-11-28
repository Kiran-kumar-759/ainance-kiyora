import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BankingProviderInfo(BaseModel):
    provider_id: str
    name: str
    description: str
    is_simulated: bool = True
    logo_key: str
    supported_account_types: list[str]


class BankInstitutionResponse(BaseModel):
    bank_id: str
    bank_name: str
    short_name: str
    bank_code: str
    category: str
    logo_key: str
    logo_url: str
    supported_connection_methods: list[str]
    provider_id: str
    provider_available: bool
    live_supported: bool
    is_demo: bool
    connection_availability_status: str
    description: str
    unavailable_reason: str | None = None


class BankInstitutionCatalogResponse(BaseModel):
    institutions: list[BankInstitutionResponse]
    total: int
    live_aa_configured: bool
    demo_available: bool


class BankingConsentRequest(BaseModel):
    provider_id: str = Field(..., description="Demo provider identifier")
    consent_given: bool = Field(..., description="Explicit user confirmation for simulation")


class BankingInitiateRequest(BaseModel):
    bank_id: str = Field(..., min_length=2, max_length=60, description="Catalog bank_id or demo provider_id")
    connection_method: Literal["demo", "account_aggregator"] = Field(
        default="demo",
        description="Connection method ('demo' for simulated banks; 'account_aggregator' when configured)",
    )
    consent_given: bool = Field(
        default=False,
        description="If false, connection starts in awaiting_consent stage until explicit consent call",
    )


class BankingConsentDecisionRequest(BaseModel):
    consent_given: bool = Field(..., description="Whether user grants read-only account & transaction consent")
    consent_scope: str = Field(default="accounts,transactions", max_length=100)


class BankingConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: str
    bank_id: str | None = None
    connection_method: str = "demo"
    institution_name: str
    status: str
    lifecycle_state: str = "connected"
    consent_granted_at: dt.datetime
    is_simulated: bool
    last_sync_at: dt.datetime | None = None
    last_error: str | None = None
    revoked_at: dt.datetime | None = None
    created_at: dt.datetime
    connected_accounts_count: int = 0


class DiscoveredAccountInfo(BaseModel):
    external_account_id: str
    name: str
    account_type: str
    institution_name: str
    masked_account_number: str
    balance: Decimal
    currency: str = "INR"
    already_imported: bool = False


class BankingAccountImportRequest(BaseModel):
    account_ids: list[str] = Field(
        ..., min_length=1, description="List of external account IDs to import"
    )
    trigger_initial_sync: bool = Field(
        default=False,
        description="Optionally perform initial idempotent transaction synchronization immediately",
    )


class BankingSyncResponse(BaseModel):
    connection_id: uuid.UUID
    status: str
    lifecycle_state: str = "connected"
    accounts_synced: int
    transactions_synced: int
    synced_at: dt.datetime
    message: str


class BankingSyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    status: str
    accounts_synced: int
    transactions_synced: int
    error_message: str | None = None
    started_at: dt.datetime
    completed_at: dt.datetime | None = None
