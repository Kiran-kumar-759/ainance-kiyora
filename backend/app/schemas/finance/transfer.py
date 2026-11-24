import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransferCreateRequest(BaseModel):
    source_account_id: uuid.UUID = Field(...)
    destination_account_id: uuid.UUID = Field(...)
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Positive transfer amount")
    currency: str = Field("INR", max_length=3)
    transfer_date: dt.date = Field(...)
    description: str | None = Field(None, max_length=255)


class TransferReverseRequest(BaseModel):
    reason: str = Field("User requested transfer reversal", min_length=1, max_length=255)


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    source_account_id: uuid.UUID
    source_account_name: str | None = None
    destination_account_id: uuid.UUID
    destination_account_name: str | None = None
    amount: Decimal
    currency: str
    transfer_date: dt.date
    description: str | None = None
    status: str
    reversal_reason: str | None = None
    reversed_at: dt.datetime | None = None
    created_at: dt.datetime
