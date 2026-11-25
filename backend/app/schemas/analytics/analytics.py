import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.analytics.common import (
    CalculationMetadata,
    ComparisonMetric,
    PeriodBounds,
    TimeSeriesPoint,
)
from app.schemas.finance.transaction import TransactionResponse


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID | None = None
    category_name: str
    category_color: str | None = None
    total_amount: Decimal
    percentage: Decimal
    transaction_count: int
    average_amount: Decimal


class SourceDistributionItem(BaseModel):
    source: str
    label: str
    total_amount: Decimal
    percentage: Decimal
    transaction_count: int


class AccountBreakdownItem(BaseModel):
    account_id: uuid.UUID
    account_name: str
    account_type: str
    total_amount: Decimal
    percentage: Decimal
    transaction_count: int


class BalanceTrendPoint(BaseModel):
    date: dt.date
    label: str
    assets_balance: Decimal
    liabilities_balance: Decimal
    net_position: Decimal


class CategoryComparisonItem(BaseModel):
    category_id: uuid.UUID | None = None
    category_name: str
    category_color: str | None = None
    comparison: ComparisonMetric


class CategorySeriesPoint(BaseModel):
    category_id: uuid.UUID | None = None
    category_name: str
    category_color: str | None = None
    points: list[dict[str, str]]  # bucket_key -> Decimal string or label/amount pairs


class IncomeAnalyticsResponse(BaseModel):
    period_bounds: PeriodBounds
    granularity: str
    total_income: Decimal
    transaction_count: int
    by_category: list[CategoryBreakdownItem]
    by_account: list[AccountBreakdownItem]
    by_source: list[SourceDistributionItem]
    trend: list[TimeSeriesPoint]
    comparison: ComparisonMetric
    traceability: CalculationMetadata


class ExpenseAnalyticsResponse(BaseModel):
    period_bounds: PeriodBounds
    granularity: str
    total_expenses: Decimal
    transaction_count: int
    average_daily_spend: Decimal
    average_monthly_spend: Decimal | None = None
    by_category: list[CategoryBreakdownItem]
    by_account: list[AccountBreakdownItem]
    by_source: list[SourceDistributionItem]
    trend: list[TimeSeriesPoint]
    largest_expenses: list[TransactionResponse]
    comparison: ComparisonMetric
    traceability: CalculationMetadata


class CashFlowAnalyticsResponse(BaseModel):
    period_bounds: PeriodBounds
    granularity: str
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    savings_rate_pct: Decimal | None = None
    series: list[TimeSeriesPoint]
    traceability: CalculationMetadata


class CategoryAnalyticsResponse(BaseModel):
    period_bounds: PeriodBounds
    category_type: Literal["expense", "income"]
    total_amount: Decimal
    transaction_count: int
    items: list[CategoryBreakdownItem]
    traceability: CalculationMetadata


class TrendAnalyticsResponse(BaseModel):
    period_bounds: PeriodBounds
    granularity: str
    series: list[TimeSeriesPoint]
    top_category_trends: list[dict[str, object]]
    balance_history: list[BalanceTrendPoint]
    balance_history_available: bool
    balance_history_note: str
    traceability: CalculationMetadata


class PeriodComparisonResponse(BaseModel):
    comparison_preset: str
    current_period: PeriodBounds
    previous_period: PeriodBounds
    income: ComparisonMetric
    expenses: ComparisonMetric
    net_savings: ComparisonMetric
    savings_rate_current: Decimal | None = None
    savings_rate_previous: Decimal | None = None
    category_comparisons: list[CategoryComparisonItem]
    partial_period_warning: str | None = None


class AccountAnalyticsItem(BaseModel):
    account_id: uuid.UUID
    name: str
    institution_name: str | None = None
    account_type: str
    current_balance: Decimal
    is_liability: bool
    currency: str
    source: str
    status: str
    transaction_count: int
    period_income: Decimal
    period_expenses: Decimal
    net_transaction_activity: Decimal


class AccountAnalyticsListResponse(BaseModel):
    period_bounds: PeriodBounds
    total_assets: Decimal
    total_liabilities: Decimal
    net_financial_position: Decimal
    accounts: list[AccountAnalyticsItem]


class AccountAnalyticsDetailResponse(BaseModel):
    period_bounds: PeriodBounds
    granularity: str
    account: AccountAnalyticsItem
    trend: list[TimeSeriesPoint]
    category_distribution: list[CategoryBreakdownItem]
    recent_transactions: list[TransactionResponse]
    balance_history: list[BalanceTrendPoint]
    balance_history_note: str
    traceability: CalculationMetadata
