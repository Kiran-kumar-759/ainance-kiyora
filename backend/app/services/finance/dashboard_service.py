import calendar
import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.finance import FinancialTransaction
from app.models.user import User
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.finance.account import AccountResponse
from app.schemas.finance.dashboard import FinancialDashboardResponse


class DashboardService:
    """Service providing financial overview summaries, period income/expense metrics, and net position."""

    def __init__(self):
        self.account_repo = AccountRepository()
        self.transaction_repo = TransactionRepository()

    def _get_period_bounds(self, period: str) -> tuple[dt.date, dt.date]:
        today = dt.date.today()
        if period == "last_month":
            first_of_this_month = today.replace(day=1)
            last_day_prev_month = first_of_this_month - dt.timedelta(days=1)
            start_date = last_day_prev_month.replace(day=1)
            end_date = last_day_prev_month
        elif period == "this_year":
            start_date = today.replace(month=1, day=1)
            end_date = today
        elif period == "all_time":
            start_date = dt.date(2000, 1, 1)
            end_date = today
        else:  # default this_month
            start_date = today.replace(day=1)
            _, last_day = calendar.monthrange(today.year, today.month)
            end_date = today.replace(day=last_day)
        return start_date, end_date

    def get_dashboard_summary(
        self, db: Session, user: User, period: str = "this_month"
    ) -> FinancialDashboardResponse:
        start_date, end_date = self._get_period_bounds(period)

        # Retrieve user's accounts
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=False)
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")

        for acc in accounts:
            if acc.account_type == "credit_card":
                total_liabilities += acc.current_balance
            else:
                total_assets += acc.current_balance

        net_financial_position = total_assets - total_liabilities

        # Period Income
        income_stmt = select(
            func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00"))
        ).where(
            FinancialTransaction.user_id == user.id,
            FinancialTransaction.transaction_type == "income",
            FinancialTransaction.transaction_date >= start_date,
            FinancialTransaction.transaction_date <= end_date,
        )
        total_income = db.execute(income_stmt).scalar() or Decimal("0.00")

        # Period Expense
        expense_stmt = select(
            func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0.00"))
        ).where(
            FinancialTransaction.user_id == user.id,
            FinancialTransaction.transaction_type == "expense",
            FinancialTransaction.transaction_date >= start_date,
            FinancialTransaction.transaction_date <= end_date,
        )
        total_expenses = db.execute(expense_stmt).scalar() or Decimal("0.00")

        net_savings = total_income - total_expenses
        savings_rate_pct = None
        if total_income > Decimal("0.00"):
            savings_rate_pct = Decimal(round((net_savings / total_income) * Decimal("100.00"), 2))

        # Recent transactions
        recent_txs, _ = self.transaction_repo.list_transactions(
            db=db,
            user_id=user.id,
            page=1,
            page_size=8,
            sort_by="date_desc",
        )
        from app.services.finance.transaction_service import TransactionService

        tx_service = TransactionService()
        recent_tx_responses = [tx_service._to_response(tx) for tx in recent_txs]

        return FinancialDashboardResponse(
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_financial_position=net_financial_position,
            account_count=len(accounts),
            period=period,
            period_start=start_date,
            period_end=end_date,
            total_income=total_income,
            total_expenses=total_expenses,
            net_savings=net_savings,
            savings_rate_pct=savings_rate_pct,
            recent_transactions=recent_tx_responses,
            accounts=[AccountResponse.model_validate(a) for a in accounts],
        )
