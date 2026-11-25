import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── AI Provider & LLM Structured Output Schemas ────────────────────────────────

GroqCategorizationOutputCategory = str


class GroqCategorizationSchema(BaseModel):
    """Strict schema for optional Groq categorization fallback output."""

    model_config = ConfigDict(extra="forbid")

    suggested_category: str = Field(..., min_length=1, max_length=100)
    normalized_merchant: str | None = Field(None, max_length=150)
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str = Field(..., min_length=3, max_length=300)


class GroqInsightNarrativeSchema(BaseModel):
    """Strict schema for optional Groq insight narrative enrichment."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=5, max_length=800)
    suggested_action: str | None = Field(None, max_length=255)


# ── Overview & Run Requests ────────────────────────────────────────────────────


class IntelligenceRunRequest(BaseModel):
    reanalyze_all: bool = False
    use_ai_fallback: bool = True
    train_model: bool = True
    lookback_days: int = Field(default=365, ge=30, le=1825)
    async_job: bool = False


class CategorizeTransactionsRequest(BaseModel):
    transaction_ids: list[uuid.UUID] | None = None
    reanalyze_all: bool = False
    use_ai_fallback: bool = True


class CategorySummaryItem(BaseModel):
    category_name: str
    transaction_count: int
    total_amount: Decimal
    share_pct: Decimal


class OverviewMetricCard(BaseModel):
    total_analyzed_transactions: int
    total_eligible_transactions: int
    needs_review_count: int
    confirmed_count: int
    merchant_count: int
    recurring_candidate_count: int
    pending_recurring_count: int
    open_anomaly_count: int
    high_severity_anomaly_count: int
    unread_insight_count: int
    total_insight_count: int
    ml_model_status: str
    ml_model_version: str | None = None
    ml_training_samples: int = 0
    groq_enabled: bool
    groq_model: str
    last_job_status: str | None = None
    last_job_completed_at: dt.datetime | None = None


class AiModelMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model_name: str
    model_version: str
    status: str
    training_sample_count: int
    class_count: int
    accuracy: Decimal | None = None
    precision_weighted: Decimal | None = None
    recall_weighted: Decimal | None = None
    f1_weighted: Decimal | None = None
    confusion_matrix: dict[str, Any] = Field(default_factory=dict)
    evaluation_notes: str | None = None
    trained_at: dt.datetime | None = None
    updated_at: dt.datetime


class AiProcessingJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    provider_name: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    attempt_count: int
    max_attempts: int
    items_processed: int
    summary: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    created_at: dt.datetime


class IntelligenceOverviewResponse(BaseModel):
    metrics: OverviewMetricCard
    model_metadata: AiModelMetadataResponse | None = None
    recent_jobs: list[AiProcessingJobResponse] = Field(default_factory=list)
    top_categories: list[CategorySummaryItem] = Field(default_factory=list)
    top_anomalies: list["SpendingAnomalyResponse"] = Field(default_factory=list)
    top_insights: list["FinancialInsightResponse"] = Field(default_factory=list)


# ── Transaction Categorization ─────────────────────────────────────────────────


class TransactionCategorizationResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    merchant_id: uuid.UUID | None = None
    transaction_date: dt.date
    transaction_type: str
    amount: Decimal
    currency: str
    description: str | None = None
    merchant_payee: str | None = None
    normalized_merchant_name: str | None = None
    current_category_id: uuid.UUID | None = None
    current_category_name: str | None = None
    suggested_category_id: uuid.UUID | None = None
    suggested_category_name: str | None = None
    predicted_category_name: str | None = None
    classification_method: str
    confidence: Decimal
    explanation: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    model_version: str | None = None
    provider_name: str | None = None
    review_status: str
    analyzed_at: dt.datetime
    updated_at: dt.datetime


class TransactionCategorizationListResponse(BaseModel):
    items: list[TransactionCategorizationResponse]
    total: int
    page: int
    page_size: int
    needs_review_count: int
    confirmed_count: int


class TransactionCategorizationOverrideRequest(BaseModel):
    category_id: uuid.UUID
    normalized_merchant_name: str | None = Field(None, min_length=1, max_length=150)
    save_merchant_mapping: bool = True
    action: Literal["confirm", "override", "dismiss"] = "override"
    notes: str | None = Field(None, max_length=500)


class CategorizationFeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID
    categorization_id: uuid.UUID | None = None
    action: str
    previous_category_id: uuid.UUID | None = None
    previous_category_name: str | None = None
    new_category_id: uuid.UUID | None = None
    new_category_name: str | None = None
    previous_merchant_name: str | None = None
    new_merchant_name: str | None = None
    notes: str | None = None
    created_at: dt.datetime


# ── Merchant Intelligence ──────────────────────────────────────────────────────


class MerchantAliasResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_pattern: str
    normalized_token: str
    occurrence_count: int
    created_at: dt.datetime


class MerchantIdentityResponse(BaseModel):
    id: uuid.UUID
    canonical_key: str
    normalized_name: str
    default_category_id: uuid.UUID | None = None
    default_category_name: str | None = None
    is_user_confirmed: bool
    transaction_count: int
    total_spent: Decimal
    aliases: list[MerchantAliasResponse] = Field(default_factory=list)
    updated_at: dt.datetime


class MerchantListResponse(BaseModel):
    items: list[MerchantIdentityResponse]
    total: int
    page: int
    page_size: int


class MerchantUpdateRequest(BaseModel):
    normalized_name: str | None = Field(None, min_length=1, max_length=150)
    default_category_id: uuid.UUID | None = None
    is_user_confirmed: bool | None = None
    apply_to_existing_transactions: bool = True


# ── Recurring Payment Intelligence ─────────────────────────────────────────────


class RecurringPaymentCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    merchant_id: uuid.UUID | None = None
    merchant_key: str
    merchant_name: str
    suggested_category_name: str | None = None
    commitment_type: str
    frequency: str
    estimated_amount: Decimal
    min_amount: Decimal
    max_amount: Decimal
    amount_variability_pct: Decimal
    is_variable_amount: bool
    occurrence_count: int
    first_seen_date: dt.date | None = None
    last_seen_date: dt.date | None = None
    next_expected_date: dt.date | None = None
    confidence: Decimal
    detection_method: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    review_status: str
    linked_subscription_id: uuid.UUID | None = None
    updated_at: dt.datetime


class RecurringCandidateListResponse(BaseModel):
    items: list[RecurringPaymentCandidateResponse]
    total: int
    pending_count: int
    confirmed_count: int


class RecurringCandidateDecisionRequest(BaseModel):
    decision: Literal["confirm", "reject", "link_subscription"]
    create_subscription: bool = False
    subscription_id: uuid.UUID | None = None

    @field_validator("subscription_id")
    @classmethod
    def validate_link_target(cls, v: uuid.UUID | None, info: Any) -> uuid.UUID | None:
        return v


# ── Spending Patterns ──────────────────────────────────────────────────────────


class SpendingPatternGroupItem(BaseModel):
    label: str
    amount: Decimal
    transaction_count: int
    share_pct: Decimal


class MonthlySpendingPoint(BaseModel):
    month: str
    total_expense: Decimal
    total_income: Decimal
    recurring_expense: Decimal
    non_recurring_expense: Decimal
    transaction_count: int


class WeeklySpendingPoint(BaseModel):
    week_start: dt.date
    total_expense: Decimal
    transaction_count: int


class DayOfWeekSpendingPoint(BaseModel):
    day_name: str
    day_index: int
    total_expense: Decimal
    transaction_count: int


class SpendingPatternsResponse(BaseModel):
    period_start: dt.date
    period_end: dt.date
    total_expense: Decimal
    total_income: Decimal
    recurring_total: Decimal
    non_recurring_total: Decimal
    fixed_total: Decimal
    variable_total: Decimal
    essential_total: Decimal
    discretionary_total: Decimal
    weekend_expense: Decimal
    weekday_expense: Decimal
    weekend_share_pct: Decimal
    top_merchant_concentration_pct: Decimal
    top_3_merchant_concentration_pct: Decimal
    by_category: list[SpendingPatternGroupItem] = Field(default_factory=list)
    by_merchant: list[SpendingPatternGroupItem] = Field(default_factory=list)
    monthly_trend: list[MonthlySpendingPoint] = Field(default_factory=list)
    weekly_trend: list[WeeklySpendingPoint] = Field(default_factory=list)
    day_of_week_trend: list[DayOfWeekSpendingPoint] = Field(default_factory=list)


# ── Statistical Anomaly Detection ──────────────────────────────────────────────


class SpendingAnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    merchant_name: str | None = None
    anomaly_type: str
    observed_amount: Decimal
    baseline_amount: Decimal
    deviation_pct: Decimal
    severity: str
    confidence: Decimal
    detection_method: str
    explanation: str
    supporting_transaction_ids: list[str] = Field(default_factory=list)
    review_status: str
    detected_at: dt.datetime
    reviewed_at: dt.datetime | None = None


class SpendingAnomalyListResponse(BaseModel):
    items: list[SpendingAnomalyResponse]
    total: int
    open_count: int
    acknowledged_count: int
    dismissed_count: int


class AnomalyReviewRequest(BaseModel):
    action: Literal["acknowledge", "dismiss", "reopen"]


# ── Evidence-Backed Insights ───────────────────────────────────────────────────


class FinancialInsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    insight_type: str
    title: str
    description: str
    severity: str
    period_start: dt.date | None = None
    period_end: dt.date | None = None
    supporting_data: dict[str, Any] = Field(default_factory=dict)
    calculation_method: str
    provider_name: str | None = None
    confidence: Decimal
    suggested_action: str | None = None
    status: str
    generated_at: dt.datetime
    read_at: dt.datetime | None = None
    dismissed_at: dt.datetime | None = None


class FinancialInsightListResponse(BaseModel):
    items: list[FinancialInsightResponse]
    total: int
    new_count: int
    read_count: int
    dismissed_count: int


class InsightReviewRequest(BaseModel):
    action: Literal["mark_read", "dismiss", "reopen"]


IntelligenceOverviewResponse.model_rebuild()
