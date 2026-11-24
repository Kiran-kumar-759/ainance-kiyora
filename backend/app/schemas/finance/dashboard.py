import datetime as dt
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.finance.account import AccountResponse
from app.schemas.finance.transaction import TransactionResponse


class FinancialDashboardResponse(BaseModel):
    total_assets: Decimal
    total_liabilities: Decimal
    net_financial_position: Decimal
    account_count: int
    period: str
    period_start: dt.date
    period_end: dt.date
    total_income: Decimal
    total_expenses: Decimal
    net_savings: Decimal
    savings_rate_pct: Decimal | None = None
    recent_transactions: list[TransactionResponse]
    accounts: list[AccountResponse]
