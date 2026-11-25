import datetime as dt
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.analytics.analytics import AccountBreakdownItem, CategoryBreakdownItem
from app.schemas.analytics.common import CalculationMetadata, TimeSeriesPoint
from app.schemas.finance.transaction import TransactionResponse

ReportTypeLiteral = Literal[
    "monthly_summary",
    "income_report",
    "expense_report",
    "category_spending",
    "account_activity",
    "cash_flow",
    "savings_report",
    "transaction_summary",
]


class ReportDefinition(BaseModel):
    id: ReportTypeLiteral
    title: str
    description: str
    supports_csv_export: bool = True


class ReportListResponse(BaseModel):
    reports: list[ReportDefinition]


class ReportSummaryMetric(BaseModel):
    label: str
    value: str
    raw_decimal: Decimal | None = None
    highlight: Literal["neutral", "positive", "negative"] = "neutral"


class ReportFilterMetadata(BaseModel):
    report_type: ReportTypeLiteral
    title: str
    start_date: dt.date
    end_date: dt.date
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    transaction_type: str | None = None
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    source: str | None = None
    generated_at: dt.datetime
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"


class FinancialReportResponse(BaseModel):
    metadata: ReportFilterMetadata
    summary_metrics: list[ReportSummaryMetric]
    category_breakdown: list[CategoryBreakdownItem]
    account_breakdown: list[AccountBreakdownItem]
    cashflow_series: list[TimeSeriesPoint]
    transactions: list[TransactionResponse]
    total_transactions: int
    traceability: CalculationMetadata
