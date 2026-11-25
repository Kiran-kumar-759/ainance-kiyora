import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.analytics.analytics_repository import AnalyticsRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.finance.account import AccountResponse
from app.schemas.finance.dashboard import FinancialDashboardResponse
from app.services.analytics.period_utils import (
    compute_savings_rate,
    quantize_money,
    resolve_period_bounds,
)


class DashboardService:
    """
    Service providing backwards-compatible financial dashboard overview metrics,
    backed cleanly by AnalyticsRepository and Asia/Kolkata period resolution.
    """

    def __init__(self):
        self.account_repo = AccountRepository()
        self.transaction_repo = TransactionRepository()
        self.analytics_repo = AnalyticsRepository()

    def _get_period_bounds(
        self,
        period: str,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> tuple[dt.date, dt.date]:
        bounds = resolve_period_bounds(period=period, start_date=start_date, end_date=end_date)
        return bounds.start_date, bounds.end_date

    def get_dashboard_summary(
        self,
        db: Session,
        user: User,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> FinancialDashboardResponse:
        earliest = (
            self.analytics_repo.get_earliest_transaction_date(db, user.id)
            if period == "all_time"
            else None
        )
        bounds = resolve_period_bounds(
            period=period,
            start_date=start_date,
            end_date=end_date,
            earliest_date=earliest,
        )

        # Retrieve user's active accounts
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=False)
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")

        for acc in accounts:
            if acc.account_type in {"credit_card", "loan_liability"}:
                total_liabilities += acc.current_balance
            else:
                total_assets += acc.current_balance

        total_assets = quantize_money(total_assets)
        total_liabilities = quantize_money(total_liabilities)
        net_financial_position = quantize_money(total_assets - total_liabilities)

        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date
        )
        total_income = quantize_money(totals["income"])
        total_expenses = quantize_money(totals["expenses"])
        net_savings, savings_rate_pct = compute_savings_rate(total_income, total_expenses)

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
            period_start=bounds.start_date,
            period_end=bounds.end_date,
            total_income=total_income,
            total_expenses=total_expenses,
            net_savings=net_savings,
            savings_rate_pct=savings_rate_pct,
            recent_transactions=recent_tx_responses,
            accounts=[AccountResponse.model_validate(a) for a in accounts],
        )
