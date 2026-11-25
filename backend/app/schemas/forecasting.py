import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ConfidenceLabel = Literal["high", "medium", "low", "insufficient_data"]
HorizonDays = Literal[7, 30, 90, 180, 365]


class GenerateForecastRequest(BaseModel):
    horizon_days: int = Field(default=30, ge=7, le=365)
    force_refresh: bool = False
    async_job: bool = False
    low_balance_threshold: Decimal = Field(
        default=Decimal("5000.00"), ge=Decimal("0.00"), le=Decimal("10000000.00")
    )


class CashflowPeriodPoint(BaseModel):
    label: str
    target_date: dt.date
    is_prediction: bool
    source_kind: str  # historical_actual, known_commitment, statistical_prediction
    income_amount: Decimal | None = None
    expense_amount: Decimal | None = None
    commitment_amount: Decimal | None = None
    net_cashflow: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    projected_closing_balance: Decimal | None = None


class CashflowForecastResponse(BaseModel):
    horizon_days: int
    as_of_date: dt.date
    data_cutoff_date: dt.date | None = None
    timezone: str = "Asia/Kolkata"
    method: str
    confidence_label: ConfidenceLabel
    confidence_score: Decimal
    expected_income: Decimal | None = None
    expected_expense: Decimal | None = None
    known_commitments_total: Decimal = Decimal("0.00")
    unknown_variable_commitments_count: int = 0
    predicted_net_cashflow: Decimal | None = None
    expected_opening_balance: Decimal = Decimal("0.00")
    projected_closing_balance: Decimal | None = None
    daily_points: list[CashflowPeriodPoint] = Field(default_factory=list)
    monthly_points: list[CashflowPeriodPoint] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ExpenseForecastResponse(BaseModel):
    horizon_days: int
    method: str
    confidence_label: ConfidenceLabel
    confidence_score: Decimal
    predicted_total: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    historical_monthly_avg: Decimal | None = None
    recent_monthly_avg: Decimal | None = None
    trend_pct: Decimal | None = None
    next_week_estimate: Decimal | None = None
    current_month_expected: Decimal | None = None
    next_month_estimate: Decimal | None = None
    quarterly_estimate: Decimal | None = None
    yearly_estimate: Decimal | None = None
    explanation: str


class IncomeForecastResponse(BaseModel):
    horizon_days: int
    method: str
    income_pattern: str  # regular_monthly, multi_source_regular, irregular, insufficient_data
    confidence_label: ConfidenceLabel
    confidence_score: Decimal
    predicted_total: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    monthly_estimate: Decimal | None = None
    historical_monthly_avg: Decimal | None = None
    observation_count: int = 0
    explanation: str


class CategoryForecastItem(BaseModel):
    category_id: str | None = None
    category_name: str
    historical_monthly_avg: Decimal
    recent_monthly_spend: Decimal
    predicted_amount: Decimal | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    expected_change_pct: Decimal | None = None
    confidence_label: ConfidenceLabel
    data_sufficient: bool
    observation_count: int
    explanation: str


class CommitmentForecastItem(BaseModel):
    source_type: str  # bill, bill_schedule, subscription, loan_installment, recurring_candidate
    source_id: str
    name: str
    due_date: dt.date
    frequency: str
    expected_amount: Decimal | None = None
    amount_certainty: str  # confirmed_fixed, estimated_variable, unknown_amount, unconfirmed_candidate
    commitment_status: str  # confirmed, unconfirmed_candidate
    category_name: str | None = None
    account_id: str | None = None
    account_name: str | None = None


class AccountBalanceProjectionPoint(BaseModel):
    target_date: dt.date
    label: str
    projected_balance: Decimal
    is_prediction: bool


class AccountBalanceForecastItem(BaseModel):
    account_id: str
    account_name: str
    account_type: str
    is_liability: bool
    current_balance: Decimal
    projected_end_balance: Decimal | None = None
    min_projected_balance: Decimal | None = None
    projected_change: Decimal | None = None
    confidence_label: ConfidenceLabel
    assumptions: list[str] = Field(default_factory=list)
    points: list[AccountBalanceProjectionPoint] = Field(default_factory=list)


class RiskWarningItem(BaseModel):
    risk_type: str  # low_balance, negative_cashflow, commitment_cluster, category_surge
    severity: Literal["high", "medium", "low"]
    title: str
    description: str
    target_date: dt.date | None = None
    projected_impact_amount: Decimal | None = None
    confidence_label: ConfidenceLabel
    contributing_records: list[dict[str, str]] = Field(default_factory=list)


class SavingsForecastResponse(BaseModel):
    horizon_days: int
    confidence_label: ConfidenceLabel
    historical_monthly_savings: Decimal | None = None
    expected_monthly_savings: Decimal | None = None
    expected_savings_rate_pct: Decimal | None = None
    projected_horizon_savings: Decimal | None = None
    projected_yearly_savings: Decimal | None = None
    conservative_monthly_savings: Decimal | None = None
    best_case_monthly_savings: Decimal | None = None
    disclaimer: str


class ForecastExplanationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    explanation_type: str
    title: str
    narrative: str
    confidence_label: str
    supporting_refs: dict[str, Any] = Field(default_factory=dict)


class ForecastRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    forecast_type: str
    horizon_days: int
    as_of_date: dt.date
    data_cutoff_date: dt.date | None = None
    timezone: str
    method: str
    method_version: str
    confidence_label: ConfidenceLabel
    confidence_score: Decimal
    observation_count: int
    historical_days_covered: int
    status: str
    evaluation_status: str
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: dt.datetime


class ForecastingOverviewResponse(BaseModel):
    forecast: ForecastRecordResponse
    cashflow: CashflowForecastResponse
    expenses: ExpenseForecastResponse
    income: IncomeForecastResponse
    categories: list[CategoryForecastItem] = Field(default_factory=list)
    commitments: list[CommitmentForecastItem] = Field(default_factory=list)
    balances: list[AccountBalanceForecastItem] = Field(default_factory=list)
    risks: list[RiskWarningItem] = Field(default_factory=list)
    savings: SavingsForecastResponse
    explanations: list[ForecastExplanationItem] = Field(default_factory=list)
    is_stale: bool = False


class ForecastScenarioRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    horizon_days: int = Field(default=30, ge=7, le=365)
    income_delta_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("-100.00"), le=Decimal("500.00")
    )
    expense_delta_pct: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("-100.00"), le=Decimal("500.00")
    )
    extra_recurring_monthly_expense: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("10000000.00")
    )
    extra_loan_payment_monthly: Decimal = Field(
        default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("10000000.00")
    )
    cancelled_subscription_ids: list[uuid.UUID] = Field(default_factory=list)
    category_adjustments_pct: dict[str, Decimal] = Field(default_factory=dict)
    save_scenario: bool = True


class ForecastScenarioOutcome(BaseModel):
    expected_income: Decimal
    expected_expense: Decimal
    known_commitments: Decimal
    net_cashflow: Decimal
    projected_savings: Decimal
    projected_closing_balance: Decimal


class ForecastScenarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    name: str
    horizon_days: int
    parameters: dict[str, Any]
    baseline_summary: ForecastScenarioOutcome
    scenario_summary: ForecastScenarioOutcome
    delta_summary: dict[str, Decimal]
    created_at: dt.datetime | None = None


class CategoryEvaluationMetric(BaseModel):
    category_name: str
    predicted_amount: Decimal
    actual_amount: Decimal
    absolute_error: Decimal


class ForecastEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    forecast_type: str
    horizon_days: int
    cutoff_date: dt.date
    eval_start_date: dt.date
    eval_end_date: dt.date
    method: str
    status: str
    predicted_expense: Decimal | None = None
    actual_expense: Decimal | None = None
    predicted_income: Decimal | None = None
    actual_income: Decimal | None = None
    predicted_net: Decimal | None = None
    actual_net: Decimal | None = None
    mae_expense: Decimal | None = None
    rmse_expense: Decimal | None = None
    wape_expense_pct: Decimal | None = None
    bias_expense: Decimal | None = None
    category_metrics: list[CategoryEvaluationMetric] = Field(default_factory=list)
    notes: str | None = None
    evaluated_at: dt.datetime
