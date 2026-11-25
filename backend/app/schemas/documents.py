import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentCategory = Literal[
    "electricity_bill",
    "water_bill",
    "gas_bill",
    "internet_bill",
    "mobile_bill",
    "credit_card_statement",
    "bank_statement",
    "shopping_receipt",
    "travel_receipt",
    "medical_receipt",
    "insurance",
    "tax",
    "loan",
    "subscription_invoice",
    "other",
]

ProcessingStatus = Literal[
    "uploaded",
    "queued",
    "processing",
    "extracted",
    "needs_review",
    "confirmed",
    "rejected",
    "failed",
]

OcrStatus = Literal["pending", "queued", "processing", "completed", "failed", "skipped"]


class LineItemSchema(BaseModel):
    description: str = Field(..., min_length=1, max_length=300)
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total: Decimal | None = None


class DocumentExtractionUpdateRequest(BaseModel):
    merchant_name: str | None = Field(None, max_length=150)
    merchant_address: str | None = Field(None, max_length=500)
    merchant_phone: str | None = Field(None, max_length=40)
    invoice_number: str | None = Field(None, max_length=100)
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    payment_date: dt.date | None = None
    bill_period: str | None = Field(None, max_length=100)
    detected_document_type: str | None = Field(None, max_length=40)
    currency: str | None = Field(None, max_length=3)

    subtotal: Decimal | None = Field(None, ge=0)
    taxable_amount: Decimal | None = Field(None, ge=0)
    total_tax: Decimal | None = Field(None, ge=0)
    grand_total: Decimal | None = Field(None, ge=0)
    amount_paid: Decimal | None = Field(None, ge=0)
    outstanding_amount: Decimal | None = Field(None, ge=0)

    gstin: str | None = Field(None, max_length=20)
    cgst: Decimal | None = Field(None, ge=0)
    sgst: Decimal | None = Field(None, ge=0)
    igst: Decimal | None = Field(None, ge=0)
    tax_percentage: Decimal | None = Field(None, ge=0, le=100)

    line_items: list[LineItemSchema] | None = None
    field_decisions: dict[str, Literal["accepted", "rejected", "edited"]] | None = None
    notes: str | None = Field(None, max_length=500)

    @field_validator("currency")
    @classmethod
    def norm_currency(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class DocumentLinkRequest(BaseModel):
    target_type: Literal["bill", "transaction", "subscription", "loan"]
    target_id: uuid.UUID


class DocumentConfirmRequest(BaseModel):
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

    # Optional overrides when creating a bill or transaction from confirmed document
    bill_name: str | None = Field(None, max_length=150)
    bill_category: str | None = Field(None, max_length=40)
    due_date: dt.date | None = None
    amount: Decimal | None = Field(None, gt=0)
    financial_account_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    transaction_type: Literal["expense", "income"] = "expense"
    transaction_date: dt.date | None = None
    description: str | None = Field(None, max_length=255)
    notes: str | None = Field(None, max_length=500)


class DocumentRejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class DocumentProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    document_filename: str | None = None
    job_type: str
    status: str
    attempt_count: int
    max_attempts: int
    next_retry_at: dt.datetime | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    error_message: str | None = None
    created_at: dt.datetime


class DocumentReviewEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    changes: dict[str, Any]
    notes: str | None = None
    created_at: dt.datetime


class DocumentLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: str
    link_role: str
    bill_id: uuid.UUID | None = None
    transaction_id: uuid.UUID | None = None
    subscription_id: uuid.UUID | None = None
    loan_id: uuid.UUID | None = None
    target_label: str | None = None
    created_at: dt.datetime


class DocumentExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    ocr_engine: str
    ocr_engine_version: str | None = None
    raw_text: str | None = None
    raw_structured_data: dict[str, Any] | None = None

    merchant_name: str | None = None
    merchant_address: str | None = None
    merchant_phone: str | None = None
    invoice_number: str | None = None
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None
    payment_date: dt.date | None = None
    bill_period: str | None = None
    detected_document_type: str | None = None

    currency: str | None = None
    subtotal: Decimal | None = None
    taxable_amount: Decimal | None = None
    total_tax: Decimal | None = None
    grand_total: Decimal | None = None
    amount_paid: Decimal | None = None
    outstanding_amount: Decimal | None = None

    gstin: str | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    tax_percentage: Decimal | None = None

    line_items: list[dict[str, Any]] = []
    field_confidence: dict[str, float] = {}
    field_decisions: dict[str, str] = {}
    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    processing_metadata: dict[str, Any] = {}
    overall_confidence: Decimal | None = None
    extracted_at: dt.datetime
    updated_at: dt.datetime


class FinancialDocumentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_type: str
    content_type: str
    file_size: int
    file_hash: str
    document_category: str
    source: str
    is_duplicate_of_id: uuid.UUID | None = None
    duplicate_flag: bool
    processing_status: str
    ocr_status: str
    page_count: int | None = None
    rejection_reason: str | None = None
    uploaded_at: dt.datetime
    processed_at: dt.datetime | None = None
    confirmed_at: dt.datetime | None = None
    rejected_at: dt.datetime | None = None
    links: list[DocumentLinkResponse] = []
    merchant_name: str | None = None
    grand_total: Decimal | None = None
    invoice_date: dt.date | None = None
    due_date: dt.date | None = None


class FinancialDocumentDetailResponse(FinancialDocumentSummaryResponse):
    extraction: DocumentExtractionResponse | None = None
    jobs: list[DocumentProcessingJobResponse] = []
    review_events: list[DocumentReviewEventResponse] = []


class DocumentListResponse(BaseModel):
    items: list[FinancialDocumentSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentOverviewResponse(BaseModel):
    total_documents: int
    processed_count: int
    needs_review_count: int
    processing_count: int
    failed_count: int
    confirmed_count: int
    rejected_count: int
    recent_documents: list[FinancialDocumentSummaryResponse]


class DocumentProcessingHistoryResponse(BaseModel):
    items: list[DocumentProcessingJobResponse]
    total: int
