import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EmailConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    provider: str = "gmail"
    email_address: str | None = None
    status: str = "disconnected"
    oauth_configured: bool = False
    scopes: list[str] = []
    last_history_id: str | None = None
    last_sync_at: dt.datetime | None = None
    last_error: str | None = None


class GmailConnectUrlResponse(BaseModel):
    authorization_url: str
    state: str
    scopes: list[str]


class EmailSyncRequest(BaseModel):
    search_query: str | None = Field(None, max_length=300)
    max_messages: int | None = Field(None, ge=1, le=50)
    force_full_query: bool = False


class EmailSyncHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    sync_mode: str
    status: str
    messages_scanned: int
    relevant_messages: int
    attachments_processed: int
    duplicate_candidates: int
    candidates_needing_review: int
    failed_jobs: int
    start_history_id: str | None = None
    end_history_id: str | None = None
    error_message: str | None = None
    started_at: dt.datetime
    completed_at: dt.datetime | None = None


class EmailAttachmentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    file_size: int
    file_hash: str | None = None
    document_id: uuid.UUID | None = None
    is_supported: bool
    processing_status: str


class EmailMessageSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_message_id: str
    sender: str | None = None
    subject: str | None = None
    received_at: dt.datetime | None = None
    snippet_text: str | None = None
    body_text: str | None = None
    relevance_category: str | None = None
    attachments: list[EmailAttachmentSummaryResponse] = []


class EmailCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    connection_id: uuid.UUID
    message_id: uuid.UUID
    attachment_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    status: str
    duplicate_status: str
    duplicate_reason: str | None = None
    merchant_name: str | None = None
    invoice_number: str | None = None
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    amount: Decimal | None = None
    currency: str | None = None
    extracted_summary: dict[str, Any] = {}
    created_at: dt.datetime
    reviewed_at: dt.datetime | None = None
    message: EmailMessageSummaryResponse | None = None


class EmailCandidateConfirmRequest(BaseModel):
    action: Literal[
        "standalone",
        "create_bill",
        "create_transaction",
        "link_bill",
        "link_transaction",
        "link_subscription",
        "link_loan",
    ] = "standalone"
    target_id: uuid.UUID | None = None
    merchant_name: str | None = Field(None, max_length=150)
    invoice_number: str | None = Field(None, max_length=100)
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    amount: Decimal | None = Field(None, gt=0)
    bill_name: str | None = Field(None, max_length=150)
    bill_category: str | None = Field(None, max_length=40)
    financial_account_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    notes: str | None = Field(None, max_length=500)


class EmailCandidateRejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class SmsIngestionStatusResponse(BaseModel):
    enabled: bool = False
    provider: str = "none"
    available: bool = False
    outgoing_reminders_active: bool = True
    limitation_reason: str
    supported_platforms_note: str
