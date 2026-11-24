import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AccountType = Literal["savings", "current", "cash", "credit_card", "digital_wallet", "other"]
AccountStatus = Literal["active", "archived"]
AccountSource = Literal["manual", "demo_bank"]


class AccountCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    account_type: AccountType = Field(...)
    institution_name: str | None = Field(None, max_length=100)
    account_identifier: str | None = Field(None, max_length=50)
    currency: str = Field("INR", max_length=3)
    opening_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Starting balance or initial credit liability",
    )


class AccountUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    account_type: AccountType | None = None
    institution_name: str | None = Field(None, max_length=100)
    account_identifier: str | None = Field(None, max_length=50)


class AccountOpeningBalanceUpdateRequest(BaseModel):
    opening_balance: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Corrected opening balance. Updates ledger and recalculates account balances.",
    )


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    account_type: str
    institution_name: str | None = None
    account_identifier: str | None = None
    currency: str
    opening_balance: Decimal
    current_balance: Decimal
    status: str
    source: str
    created_at: dt.datetime
    updated_at: dt.datetime


class AccountSummaryResponse(BaseModel):
    total_accounts: int
    active_accounts: int
    total_assets: Decimal
    total_credit_liabilities: Decimal
    net_position: Decimal
