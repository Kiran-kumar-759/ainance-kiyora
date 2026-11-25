import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BankingProviderInfo(BaseModel):
    provider_id: str
    name: str
    description: str
    is_simulated: bool = True
    logo_key: str
    supported_account_types: list[str]


class BankingConsentRequest(BaseModel):
    provider_id: str = Field(..., description="Demo provider identifier")
    consent_given: bool = Field(..., description="Explicit user confirmation for simulation")


class BankingConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: str
    institution_name: str
    status: str
    consent_granted_at: dt.datetime
    is_simulated: bool
    last_sync_at: dt.datetime | None = None
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


class BankingSyncResponse(BaseModel):
    connection_id: uuid.UUID
    status: str
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
