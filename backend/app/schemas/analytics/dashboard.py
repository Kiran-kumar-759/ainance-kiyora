from decimal import Decimal

from pydantic import BaseModel

from app.schemas.analytics.analytics import AccountAnalyticsItem, CategoryBreakdownItem
from app.schemas.analytics.common import (
    CalculationMetadata,
    ComparisonMetric,
    PeriodBounds,
    TimeSeriesPoint,
)
from app.schemas.finance.account import AccountResponse
from app.schemas.finance.transaction import TransactionResponse


class AnalyticsDashboardResponse(BaseModel):
    # Authoritative current balance sheet positions (independent of transaction period filter)
    total_assets: Decimal
    total_liabilities: Decimal
    net_financial_position: Decimal
    account_count: int
    balance_as_of_note: str = (
        "Account balances and net financial position reflect real-time ledger balances."
    )

    # Period transaction metrics
    period_bounds: PeriodBounds
    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    savings_rate_pct: Decimal | None = None

    # Period-over-period comparisons
    income_comparison: ComparisonMetric
    expense_comparison: ComparisonMetric
    savings_comparison: ComparisonMetric

    # Chart series & breakdowns
    income_vs_expense_series: list[TimeSeriesPoint]
    spending_by_category: list[CategoryBreakdownItem]
    monthly_spending_trend: list[TimeSeriesPoint]
    account_balances: list[AccountAnalyticsItem]

    # Raw records & traceability
    accounts: list[AccountResponse]
    recent_transactions: list[TransactionResponse]
    is_empty_state: bool = False
    traceability: CalculationMetadata
