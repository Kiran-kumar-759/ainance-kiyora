import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TransactionType = Literal["income", "expense", "transfer"]
TransactionSource = Literal[
    "manual",
    "demo_bank",
    "csv_import",
    "xlsx_import",
    "bill_payment",
    "subscription_payment",
    "loan_payment",
]


class TransactionCreateRequest(BaseModel):
    account_id: uuid.UUID = Field(...)
    transaction_type: Literal["income", "expense"] = Field(...)
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Positive non-zero amount")
    currency: str = Field("INR", max_length=3)
    category_id: uuid.UUID | None = Field(None)
    description: str = Field(..., min_length=1, max_length=255)
    merchant_payee: str | None = Field(None, max_length=150)
    transaction_date: dt.date = Field(...)
    notes: str | None = Field(None)


class TransactionUpdateRequest(BaseModel):
    amount: Decimal | None = Field(None, gt=Decimal("0.00"))
    category_id: uuid.UUID | None = None
    description: str | None = Field(None, min_length=1, max_length=255)
    merchant_payee: str | None = Field(None, max_length=150)
    transaction_date: dt.date | None = None
    notes: str | None = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str | None = None
    transaction_type: str
    amount: Decimal
    currency: str
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    category_icon: str | None = None
    category_color: str | None = None
    description: str
    merchant_payee: str | None = None
    transaction_date: dt.date
    notes: str | None = None
    source: str
    external_reference: str | None = None
    import_batch_id: uuid.UUID | None = None
    import_row_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
