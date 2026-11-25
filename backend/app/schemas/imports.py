import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ImportMappingConfig(BaseModel):
    date_column: str = Field(..., min_length=1)
    description_column: str = Field(..., min_length=1)
    amount_mode: Literal["single", "split"] = "single"
    amount_column: str | None = None
    debit_column: str | None = None
    credit_column: str | None = None
    type_column: str | None = None
    sign_convention: Literal["negative_is_expense", "positive_is_expense"] = "negative_is_expense"
    reference_column: str | None = None
    balance_column: str | None = None
    merchant_column: str | None = None
    notes_column: str | None = None
    currency_column: str | None = None
    date_format: Literal["auto", "DD/MM/YYYY", "DD-MM-YYYY", "YYYY-MM-DD", "DD MMM YYYY", "MM/DD/YYYY"] = "auto"
    default_currency: str = Field("INR", min_length=3, max_length=3)
    sheet_name: str | None = None
    header_row_index: int | None = Field(None, ge=0, le=50)
    delimiter: str | None = Field(None, max_length=3)
    save_profile_name: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_amount_columns(self) -> "ImportMappingConfig":
        if self.amount_mode == "single" and not self.amount_column:
            raise ValueError("Amount column must be mapped when using single amount mode.")
        if self.amount_mode == "split" and not (self.debit_column or self.credit_column):
            raise ValueError(
                "At least one of Debit or Credit column must be mapped in split amount mode."
            )
        return self


class ImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    account_name: str | None = None
    account_type: str | None = None
    original_filename: str
    file_hash: str
    file_size: int
    file_type: str
    status: str
    sheet_name: str | None = None
    header_row_index: int
    delimiter: str | None = None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    needs_review_rows: int
    duplicate_rows: int
    potential_duplicate_rows: int
    imported_rows: int
    skipped_rows: int
    total_income: Decimal
    total_expenses: Decimal
    mapping_configuration: dict[str, Any] | None = None
    lifecycle_history: list[dict[str, Any]] = []
    failure_reason: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    completed_at: dt.datetime | None = None


class ImportCenterOverviewResponse(BaseModel):
    total_imports: int
    completed_imports: int
    failed_imports: int
    transactions_imported: int
    batches: list[ImportBatchResponse]


class ImportPreviewResponse(BaseModel):
    batch: ImportBatchResponse
    available_sheets: list[str]
    selected_sheet: str
    header_row_index: int
    delimiter: str | None = None
    columns: list[str]
    preview_rows: list[list[str]]
    sample_mapped_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, Any]


class ImportMappingProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_name: str
    file_format: str
    mapping_configuration: dict[str, Any]
    created_at: dt.datetime


class ImportColumnsResponse(BaseModel):
    batch_id: uuid.UUID
    file_type: str
    available_sheets: list[str]
    selected_sheet: str
    header_row_index: int
    columns: list[str]
    sample_mapped_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, Any]
    current_mapping: dict[str, Any] | None = None
    saved_profiles: list[ImportMappingProfileResponse] = []


class ImportRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    import_batch_id: uuid.UUID
    source_row_number: int
    raw_row_data: dict[str, Any]
    normalized_date: dt.date | None = None
    normalized_description: str | None = None
    normalized_merchant: str | None = None
    normalized_notes: str | None = None
    normalized_amount: Decimal | None = None
    normalized_type: str | None = None
    currency: str
    transaction_reference: str | None = None
    running_balance: Decimal | None = None
    row_fingerprint: str | None = None
    validation_status: str
    duplicate_status: str
    duplicate_match_transaction_id: uuid.UUID | None = None
    duplicate_match_row_id: uuid.UUID | None = None
    validation_errors: list[str] = []
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    is_selected: bool
    review_changes: dict[str, Any] | None = None
    imported_transaction_id: uuid.UUID | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class ImportRowListResponse(BaseModel):
    items: list[ImportRowResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ImportRowUpdateRequest(BaseModel):
    normalized_date: dt.date | None = None
    normalized_description: str | None = Field(None, min_length=1, max_length=255)
    normalized_merchant: str | None = Field(None, max_length=150)
    normalized_notes: str | None = None
    normalized_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    normalized_type: Literal["income", "expense"] | None = None
    category_id: uuid.UUID | None = None
    clear_category: bool = False
    is_selected: bool | None = None
    exclude: bool | None = None


class ImportDuplicateReviewRequest(BaseModel):
    decision: Literal["import", "skip"]


class ImportBulkSelectRequest(BaseModel):
    action: Literal["select_all_valid", "deselect_all", "set_selection"]
    row_ids: list[uuid.UUID] | None = None
    is_selected: bool = True


class ImportSummaryResponse(BaseModel):
    batch_id: uuid.UUID
    status: str
    account_id: uuid.UUID
    account_name: str
    account_type: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    needs_review_rows: int
    duplicate_rows: int
    potential_duplicate_rows: int
    excluded_rows: int
    imported_rows: int
    selected_rows: int
    selected_income: Decimal
    selected_expenses: Decimal
    selected_net: Decimal
    imported_income: Decimal
    imported_expenses: Decimal
    imported_net: Decimal


class ImportCommitResponse(BaseModel):
    batch: ImportBatchResponse
    summary: ImportSummaryResponse
    imported_count: int
    skipped_count: int
    message: str
