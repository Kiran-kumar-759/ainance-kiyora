import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class PeriodBounds(BaseModel):
    period: str
    label: str
    start_date: dt.date
    end_date: dt.date
    timezone: str = "Asia/Kolkata"
    is_partial_period: bool = False
    days_in_period: int
    elapsed_days: int


class CalculationMetadata(BaseModel):
    formula: str
    included_transaction_count: int
    excluded_transfer_count: int
    excluded_reversed_count: int
    currency: str = "INR"
    notes: str | None = None


class ComparisonMetric(BaseModel):
    current_value: Decimal
    previous_value: Decimal
    absolute_difference: Decimal
    percentage_change: Decimal | None = None
    trend_direction: Literal["up", "down", "flat"]
    is_zero_baseline: bool = False
    comparison_note: str | None = None


class TimeSeriesPoint(BaseModel):
    bucket_key: str
    label: str
    start_date: dt.date
    end_date: dt.date
    income: Decimal
    expenses: Decimal
    net_savings: Decimal
    savings_rate_pct: Decimal | None = None
