import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

BillCategoryLiteral = Literal[
    "electricity",
    "water",
    "gas",
    "internet",
    "mobile_postpaid",
    "mobile_recharge",
    "rent",
    "insurance",
    "loan_emi",
    "credit_card",
    "maintenance",
    "other",
]

BillTypeLiteral = Literal["one_time", "recurring"]
BillFrequencyLiteral = Literal[
    "weekly", "monthly", "quarterly", "half_yearly", "yearly", "custom"
]
PaymentMethodLiteral = Literal[
    "upi",
    "debit_card",
    "credit_card",
    "net_banking",
    "cash",
    "bank_transfer",
    "auto_debit",
    "other",
]
BillDerivedStatusLiteral = Literal[
    "upcoming", "due_soon", "overdue", "paid", "partially_paid", "archived"
]


class NotificationChannelsConfig(BaseModel):
    in_app: bool = True
    email: bool = False
    sms: bool = False


class BillCreateRequest(BaseModel):
    bill_name: str = Field(..., min_length=1, max_length=150)
    bill_category: BillCategoryLiteral = "electricity"
    provider_name: str | None = Field(None, max_length=150)
    account_reference: str | None = Field(None, max_length=100)
    description: str | None = None

    bill_type: BillTypeLiteral = "one_time"
    frequency: BillFrequencyLiteral | None = None
    custom_interval_days: int | None = Field(None, ge=1, le=3650)

    is_variable_amount: bool = False
    expected_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    current_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    currency: str = Field("INR", min_length=3, max_length=3)

    due_date: dt.date
    billing_period_start: dt.date | None = None
    billing_period_end: dt.date | None = None
    end_date: dt.date | None = None

    preferred_payment_method: PaymentMethodLiteral | None = "upi"
    financial_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None

    reminder_enabled: bool = True
    reminder_days_before: list[int] = Field(default_factory=lambda: [7, 3, 1, 0])
    notification_channels: NotificationChannelsConfig = Field(
        default_factory=NotificationChannelsConfig
    )

    @model_validator(mode="after")
    def validate_bill_rules(self) -> "BillCreateRequest":
        if not self.bill_name.strip():
            raise ValueError("Bill name cannot be blank.")
        if self.currency.upper() != "INR":
            raise ValueError("Only INR currency is supported in Phase 5.")
        if not self.is_variable_amount and self.expected_amount is None and self.current_amount is None:
            raise ValueError("Fixed-amount bills require expected_amount or current_amount.")
        if self.bill_type == "recurring":
            if self.frequency is None:
                raise ValueError("Recurring bills require a frequency.")
            if self.frequency == "custom" and not self.custom_interval_days:
                raise ValueError("Custom frequency requires custom_interval_days.")
            if self.end_date is not None and self.end_date < self.due_date:
                raise ValueError("Recurrence end_date cannot be before due_date.")
        if (
            self.billing_period_start is not None
            and self.billing_period_end is not None
            and self.billing_period_end < self.billing_period_start
        ):
            raise ValueError("billing_period_end cannot be before billing_period_start.")
        cleaned_offsets = sorted({d for d in self.reminder_days_before if 0 <= d <= 60}, reverse=True)
        self.reminder_days_before = cleaned_offsets or [7, 3, 1, 0]
        return self


class BillUpdateRequest(BaseModel):
    bill_name: str | None = Field(None, min_length=1, max_length=150)
    bill_category: BillCategoryLiteral | None = None
    provider_name: str | None = Field(None, max_length=150)
    account_reference: str | None = Field(None, max_length=100)
    description: str | None = None
    is_variable_amount: bool | None = None
    expected_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    current_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    due_date: dt.date | None = None
    preferred_payment_method: PaymentMethodLiteral | None = None
    financial_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None
    reminder_enabled: bool | None = None
    reminder_days_before: list[int] | None = None
    notification_channels: NotificationChannelsConfig | None = None


class BillReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_id: uuid.UUID | None = None
    subscription_id: uuid.UUID | None = None
    loan_id: uuid.UUID | None = None
    reminder_scope: str = "bill"
    offset_days: int
    reminder_at: dt.datetime
    channels: list[str]
    is_enabled: bool
    delivery_status: str
    channel_outcomes: dict[str, Any] = {}
    retry_count: int
    max_retries: int
    next_retry_at: dt.datetime | None = None
    last_attempt_at: dt.datetime | None = None
    delivered_at: dt.datetime | None = None
    idempotency_key: str


class BillReminderUpdateRequest(BaseModel):
    reminder_enabled: bool | None = None
    reminder_days_before: list[int] | None = None
    notification_channels: NotificationChannelsConfig | None = None


class BillDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_id: uuid.UUID
    original_filename: str
    file_type: str
    content_type: str
    file_size: int
    created_at: dt.datetime


class BillPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    bill_id: uuid.UUID
    bill_name: str | None = None
    financial_account_id: uuid.UUID | None = None
    account_name: str | None = None
    transaction_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    amount_paid: Decimal
    currency: str
    payment_date: dt.date
    payment_method: str
    reference_number: str | None = None
    notes: str | None = None
    created_at: dt.datetime


class BillPaymentCreateRequest(BaseModel):
    amount_paid: Decimal = Field(
        ..., gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    payment_date: dt.date
    financial_account_id: uuid.UUID
    payment_method: PaymentMethodLiteral = "upi"
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    idempotency_key: str | None = Field(None, max_length=100)
    mark_as_fully_paid: bool = True


class BillPaymentLinkTransactionRequest(BaseModel):
    transaction_id: uuid.UUID
    payment_method: PaymentMethodLiteral = "upi"
    notes: str | None = None
    mark_as_fully_paid: bool = True


class RecurrenceScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bill_name: str
    bill_category: str
    provider_name: str | None = None
    frequency: str
    custom_interval_days: int | None = None
    anchor_day: int
    is_variable_amount: bool
    expected_amount: Decimal | None = None
    currency: str
    start_date: dt.date
    end_date: dt.date | None = None
    next_due_date: dt.date
    is_active: bool


class RecurrenceScheduleUpdateRequest(BaseModel):
    frequency: BillFrequencyLiteral | None = None
    custom_interval_days: int | None = Field(None, ge=1, le=3650)
    expected_amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    is_variable_amount: bool | None = None
    end_date: dt.date | None = None
    clear_end_date: bool = False
    is_active: bool | None = None


class BillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    parent_schedule_id: uuid.UUID | None = None
    financial_category_id: uuid.UUID | None = None
    financial_category_name: str | None = None
    linked_account_id: uuid.UUID | None = None
    linked_account_name: str | None = None

    bill_name: str
    bill_category: str
    provider_name: str | None = None
    account_reference: str | None = None
    description: str | None = None

    bill_type: str
    frequency: str | None = None
    is_variable_amount: bool
    expected_amount: Decimal | None = None
    current_amount: Decimal | None = None
    amount_paid_total: Decimal
    remaining_due: Decimal | None = None
    is_amount_unknown: bool = False
    currency: str

    billing_period_start: dt.date | None = None
    billing_period_end: dt.date | None = None
    due_date: dt.date
    paid_at: dt.datetime | None = None
    stored_status: str
    derived_status: str
    days_until_due: int

    preferred_payment_method: str | None = None
    reminder_enabled: bool
    reminder_days_before: list[int]
    notification_channels: dict[str, bool]
    is_active: bool

    created_at: dt.datetime
    updated_at: dt.datetime

    payments: list[BillPaymentResponse] = []
    reminders: list[BillReminderResponse] = []
    documents: list[BillDocumentResponse] = []
    schedule: RecurrenceScheduleResponse | None = None


class BillListResponse(BaseModel):
    items: list[BillResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class BillPaymentListResponse(BaseModel):
    items: list[BillPaymentResponse]
    total: int


class BillsOverviewResponse(BaseModel):
    upcoming_count: int
    due_soon_count: int
    overdue_count: int
    paid_count: int
    total_upcoming_known_amount: Decimal
    total_overdue_known_amount: Decimal
    total_paid_amount: Decimal
    unknown_variable_bills_count: int
    next_payment_due: BillResponse | None = None
    recent_payments: list[BillPaymentResponse] = []
    unread_notifications_count: int = 0
    due_soon_threshold_days: int


class GenerateOccurrenceResponse(BaseModel):
    created: bool
    message: str
    occurrence: BillResponse | None = None


class ProcessRemindersResponse(BaseModel):
    processed_count: int
    delivered_count: int
    partial_count: int
    unavailable_count: int
    failed_count: int
    notifications_created: int
    email_configured: bool
    sms_configured: bool


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    notification_type: str
    related_bill_id: uuid.UUID | None = None
    related_payment_id: uuid.UUID | None = None
    related_subscription_id: uuid.UUID | None = None
    related_loan_id: uuid.UUID | None = None
    is_read: bool
    read_at: dt.datetime | None = None
    created_at: dt.datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
