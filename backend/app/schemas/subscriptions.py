import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.bills import (
    BillReminderResponse,
    NotificationChannelsConfig,
    PaymentMethodLiteral,
)

SubscriptionCategoryLiteral = Literal[
    "ott_streaming",
    "music",
    "cloud_storage",
    "software_saas",
    "gaming",
    "news_media",
    "fitness",
    "delivery_membership",
    "other",
]

SubscriptionFrequencyLiteral = Literal[
    "weekly", "monthly", "quarterly", "half_yearly", "yearly", "custom"
]

SubscriptionStatusLiteral = Literal[
    "active", "trial", "paused", "cancelled", "expired", "archived"
]


class SubscriptionCreateRequest(BaseModel):
    subscription_name: str = Field(..., min_length=1, max_length=150)
    provider_name: str | None = Field(None, max_length=150)
    category: SubscriptionCategoryLiteral = "ott_streaming"
    plan_name: str | None = Field(None, max_length=100)
    description: str | None = None
    notes: str | None = None

    amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    currency: str = Field("INR", min_length=3, max_length=3)

    billing_frequency: SubscriptionFrequencyLiteral = "monthly"
    custom_interval_days: int | None = Field(None, ge=1, le=3650)

    start_date: dt.date
    next_renewal_date: dt.date | None = None
    previous_renewal_date: dt.date | None = None
    trial_start_date: dt.date | None = None
    trial_end_date: dt.date | None = None
    is_trial: bool = False

    financial_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None
    preferred_payment_method: PaymentMethodLiteral | None = "upi"

    reminder_enabled: bool = True
    reminder_days_before: list[int] = Field(default_factory=lambda: [7, 3, 1, 0])
    notification_channels: NotificationChannelsConfig = Field(
        default_factory=NotificationChannelsConfig
    )

    @model_validator(mode="after")
    def validate_rules(self) -> "SubscriptionCreateRequest":
        if not self.subscription_name.strip():
            raise ValueError("Subscription name cannot be blank.")
        if self.currency.upper() != "INR":
            raise ValueError("Only INR currency is supported in Phase 6.")
        if self.billing_frequency == "custom" and not self.custom_interval_days:
            raise ValueError("Custom billing frequency requires custom_interval_days.")
        if (
            self.trial_start_date is not None
            and self.trial_end_date is not None
            and self.trial_end_date < self.trial_start_date
        ):
            raise ValueError("Trial end date cannot be before trial start date.")
        cleaned = sorted({d for d in self.reminder_days_before if 0 <= d <= 60}, reverse=True)
        self.reminder_days_before = cleaned or [7, 3, 1, 0]
        return self


class SubscriptionUpdateRequest(BaseModel):
    subscription_name: str | None = Field(None, min_length=1, max_length=150)
    provider_name: str | None = Field(None, max_length=150)
    category: SubscriptionCategoryLiteral | None = None
    plan_name: str | None = Field(None, max_length=100)
    description: str | None = None
    notes: str | None = None
    amount: Decimal | None = Field(
        None, gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    price_change_reason: str | None = Field(None, max_length=255)
    billing_frequency: SubscriptionFrequencyLiteral | None = None
    custom_interval_days: int | None = Field(None, ge=1, le=3650)
    next_renewal_date: dt.date | None = None
    trial_end_date: dt.date | None = None
    financial_category_id: uuid.UUID | None = None
    linked_account_id: uuid.UUID | None = None
    preferred_payment_method: PaymentMethodLiteral | None = None
    reminder_enabled: bool | None = None
    reminder_days_before: list[int] | None = None
    notification_channels: NotificationChannelsConfig | None = None


class SubscriptionPriceChangeRequest(BaseModel):
    new_price: Decimal = Field(
        ..., gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    effective_date: dt.date
    reason: str | None = Field(None, max_length=255)


class SubscriptionCancelRequest(BaseModel):
    cancellation_date: dt.date | None = None
    reason: str | None = Field(None, max_length=255)


class SubscriptionPaymentCreateRequest(BaseModel):
    amount_paid: Decimal = Field(
        ..., gt=Decimal("0.00"), le=Decimal("99999999999999999.99"), decimal_places=2
    )
    payment_date: dt.date
    financial_account_id: uuid.UUID
    payment_method: PaymentMethodLiteral = "upi"
    reference_number: str | None = Field(None, max_length=100)
    notes: str | None = None
    idempotency_key: str | None = Field(None, max_length=100)
    advance_renewal_date: bool = True


class SubscriptionPaymentLinkRequest(BaseModel):
    transaction_id: uuid.UUID
    payment_method: PaymentMethodLiteral = "upi"
    notes: str | None = None
    advance_renewal_date: bool = True


class SubscriptionPaymentReverseRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=255)


class SubscriptionReminderUpdateRequest(BaseModel):
    reminder_enabled: bool | None = None
    reminder_days_before: list[int] | None = None
    notification_channels: NotificationChannelsConfig | None = None


class SubscriptionPriceHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    previous_price: Decimal | None = None
    new_price: Decimal
    effective_date: dt.date
    reason: str | None = None
    created_at: dt.datetime


class SubscriptionPaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_name: str | None = None
    financial_account_id: uuid.UUID | None = None
    account_name: str | None = None
    transaction_id: uuid.UUID | None = None
    transfer_id: uuid.UUID | None = None
    amount_paid: Decimal
    currency: str
    payment_date: dt.date
    payment_method: str
    reference_number: str | None = None
    payment_status: str
    reversal_reason: str | None = None
    notes: str | None = None
    created_at: dt.datetime


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    financial_category_id: uuid.UUID | None = None
    financial_category_name: str | None = None
    linked_account_id: uuid.UUID | None = None
    linked_account_name: str | None = None

    subscription_name: str
    provider_name: str | None = None
    category: str
    plan_name: str | None = None
    description: str | None = None
    notes: str | None = None

    amount: Decimal | None = None
    monthly_equivalent: Decimal | None = None
    annual_equivalent: Decimal | None = None
    is_amount_unknown: bool = False
    currency: str

    billing_frequency: str
    custom_interval_days: int | None = None
    anchor_day: int

    start_date: dt.date
    next_renewal_date: dt.date | None = None
    previous_renewal_date: dt.date | None = None
    trial_start_date: dt.date | None = None
    trial_end_date: dt.date | None = None
    cancellation_date: dt.date | None = None

    days_until_renewal: int | None = None
    is_renewal_due_soon: bool = False
    is_trial_ending_soon: bool = False
    preferred_payment_method: str | None = None
    status: str

    reminder_enabled: bool
    reminder_days_before: list[int]
    notification_channels: dict[str, bool]

    total_actual_paid: Decimal = Decimal("0.00")
    created_at: dt.datetime
    updated_at: dt.datetime

    price_history: list[SubscriptionPriceHistoryResponse] = []
    payments: list[SubscriptionPaymentResponse] = []
    reminders: list[BillReminderResponse] = []


class SubscriptionListResponse(BaseModel):
    items: list[SubscriptionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SubscriptionPaymentListResponse(BaseModel):
    items: list[SubscriptionPaymentResponse]
    total: int


class SubscriptionOverviewResponse(BaseModel):
    active_count: int
    trial_count: int
    paused_count: int
    cancelled_count: int
    archived_count: int
    renewals_due_soon_count: int
    trials_ending_soon_count: int
    unknown_price_active_count: int
    monthly_recurring_cost: Decimal
    annual_recurring_cost: Decimal
    actual_spent_this_month: Decimal
    actual_spent_total: Decimal
    next_renewal_subscription: SubscriptionResponse | None = None
    due_soon_threshold_days: int = 7


class CategoryBreakdownItem(BaseModel):
    name: str
    monthly_projected: Decimal
    annual_projected: Decimal
    actual_spent: Decimal
    count: int


class MonthlySpendPoint(BaseModel):
    month: str
    label: str
    actual_spent: Decimal
    payment_count: int


class SubscriptionAnalyticsResponse(BaseModel):
    monthly_recurring_cost: Decimal
    annual_recurring_cost: Decimal
    total_actual_historical_spend: Decimal
    active_subscriptions_count: int
    cancelled_subscriptions_count: int
    price_increase_events_count: int
    by_category: list[CategoryBreakdownItem] = []
    by_provider: list[CategoryBreakdownItem] = []
    monthly_trend: list[MonthlySpendPoint] = []
    most_expensive: list[SubscriptionResponse] = []
    upcoming_commitments: list[SubscriptionResponse] = []
    recent_price_changes: list[SubscriptionPriceHistoryResponse] = []


class SubscriptionCandidateResponse(BaseModel):
    merchant_key: str
    display_name: str
    estimated_amount: Decimal
    detected_frequency: str
    occurrence_count: int
    first_seen: dt.date
    last_seen: dt.date
    suggested_next_date: dt.date
    sample_transaction_ids: list[uuid.UUID] = []
    confidence_note: str


class SubscriptionCandidateActionRequest(BaseModel):
    merchant_key: str = Field(..., min_length=1, max_length=150)
    action: Literal["ignore", "link"]
    subscription_id: uuid.UUID | None = None
