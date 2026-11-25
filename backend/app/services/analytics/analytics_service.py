import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.analytics.analytics_repository import AnalyticsRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.repositories.finance.ledger_repository import LedgerRepository
from app.repositories.finance.transaction_repository import TransactionRepository
from app.schemas.analytics.analytics import (
    AccountAnalyticsDetailResponse,
    AccountAnalyticsItem,
    AccountAnalyticsListResponse,
    AccountBreakdownItem,
    BalanceTrendPoint,
    CashFlowAnalyticsResponse,
    CategoryAnalyticsResponse,
    CategoryBreakdownItem,
    CategoryComparisonItem,
    ExpenseAnalyticsResponse,
    IncomeAnalyticsResponse,
    PeriodComparisonResponse,
    SourceDistributionItem,
    TrendAnalyticsResponse,
)
from app.schemas.analytics.common import (
    CalculationMetadata,
    PeriodBounds,
    TimeSeriesPoint,
)
from app.schemas.analytics.dashboard import AnalyticsDashboardResponse
from app.schemas.finance.account import AccountResponse
from app.services.analytics.period_utils import (
    TWO_PLACES,
    _month_end,
    choose_granularity,
    compute_comparison_metric,
    compute_savings_rate,
    ist_today,
    quantize_money,
    resolve_period_bounds,
    resolve_previous_period_bounds,
)
from app.services.finance.transaction_service import TransactionService

SOURCE_LABELS: dict[str, str] = {
    "manual": "Manual Entry",
    "csv_import": "CSV Import",
    "xlsx_import": "Excel Import",
    "demo_bank": "Demo Bank Sync",
}


class AnalyticsService:
    """
    Deterministic financial analytics engine using PostgreSQL aggregations
    and LedgerRepository / FinancialTransaction sources of truth.
    """

    def __init__(self):
        self.analytics_repo = AnalyticsRepository()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.ledger_repo = LedgerRepository()
        self.transaction_repo = TransactionRepository()
        self.tx_service = TransactionService()

    def _assert_owned_account(self, db: Session, user: User, account_id: uuid.UUID):
        acc = self.account_repo.get_by_id(db, account_id, user.id)
        if not acc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial account not found.",
            )
        return acc

    def _assert_owned_category(self, db: Session, user: User, category_id: uuid.UUID):
        cat = self.category_repo.get_by_id(db, category_id, user.id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Financial category not found.",
            )
        return cat

    def _resolve_bounds_for_user(
        self,
        db: Session,
        user: User,
        period: str,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> PeriodBounds:
        earliest = None
        if period == "all_time":
            earliest = self.analytics_repo.get_earliest_transaction_date(db, user.id)
        return resolve_period_bounds(
            period=period,
            start_date=start_date,
            end_date=end_date,
            earliest_date=earliest,
        )

    def _bucket_range_and_label(self, bucket_start: dt.date, granularity: str) -> tuple[dt.date, dt.date, str]:
        if granularity == "day":
            return bucket_start, bucket_start, bucket_start.strftime("%d %b")
        if granularity == "week":
            w_end = bucket_start + dt.timedelta(days=6)
            return bucket_start, w_end, f"Wk {bucket_start.strftime('%d %b')}"
        if granularity == "quarter":
            q_num = ((bucket_start.month - 1) // 3) + 1
            q_end = _month_end(bucket_start.year, bucket_start.month + 2)
            return bucket_start, q_end, f"Q{q_num} {bucket_start.year}"
        # month
        m_end = _month_end(bucket_start.year, bucket_start.month)
        return bucket_start, m_end, bucket_start.strftime("%b %Y")

    def _align_bucket_start(self, d: dt.date, granularity: str) -> dt.date:
        if granularity == "day":
            return d
        if granularity == "week":
            return d - dt.timedelta(days=d.weekday())
        if granularity == "quarter":
            q_m = ((d.month - 1) // 3) * 3 + 1
            return dt.date(d.year, q_m, 1)
        return d.replace(day=1)

    def _next_bucket_start(self, bucket_start: dt.date, granularity: str) -> dt.date:
        if granularity == "day":
            return bucket_start + dt.timedelta(days=1)
        if granularity == "week":
            return bucket_start + dt.timedelta(days=7)
        if granularity == "quarter":
            next_m = bucket_start.month + 3
            y = bucket_start.year + ((next_m - 1) // 12)
            m = ((next_m - 1) % 12) + 1
            return dt.date(y, m, 1)
        # month
        if bucket_start.month == 12:
            return dt.date(bucket_start.year + 1, 1, 1)
        return dt.date(bucket_start.year, bucket_start.month + 1, 1)

    def _build_time_series(
        self,
        db: Session,
        user_id: uuid.UUID,
        bounds: PeriodBounds,
        granularity: str,
        account_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> list[TimeSeriesPoint]:
        raw = self.analytics_repo.get_grouped_time_series(
            db=db,
            user_id=user_id,
            start_date=bounds.start_date,
            end_date=bounds.end_date,
            granularity=granularity,
            account_id=account_id,
            category_id=category_id,
            source=source,
        )
        if not raw:
            return []

        bucket_totals: dict[dt.date, dict[str, Decimal]] = {}
        for row in raw:
            b_date = self._align_bucket_start(row["bucket"], granularity)
            slot = bucket_totals.setdefault(
                b_date, {"income": Decimal("0.00"), "expenses": Decimal("0.00")}
            )
            if row["transaction_type"] == "income":
                slot["income"] += row["total_amount"]
            elif row["transaction_type"] == "expense":
                slot["expenses"] += row["total_amount"]

        first_b = self._align_bucket_start(bounds.start_date, granularity)
        last_b = self._align_bucket_start(bounds.end_date, granularity)
        if bounds.period == "all_time":
            first_b = min(bucket_totals.keys())
            last_b = max(bucket_totals.keys())

        points: list[TimeSeriesPoint] = []
        cur = first_b
        guard = 0
        while cur <= last_b and guard < 240:
            guard += 1
            slot = bucket_totals.get(cur, {"income": Decimal("0.00"), "expenses": Decimal("0.00")})
            inc = quantize_money(slot["income"])
            exp = quantize_money(slot["expenses"])
            net, rate = compute_savings_rate(inc, exp)
            b_s, b_e, label = self._bucket_range_and_label(cur, granularity)
            points.append(
                TimeSeriesPoint(
                    bucket_key=cur.isoformat(),
                    label=label,
                    start_date=max(b_s, bounds.start_date),
                    end_date=min(b_e, bounds.end_date),
                    income=inc,
                    expenses=exp,
                    net_savings=net,
                    savings_rate_pct=rate,
                )
            )
            cur = self._next_bucket_start(cur, granularity)
        return points

    def _enrich_categories(
        self, raw_cats: list[dict], grand_total: Decimal
    ) -> list[CategoryBreakdownItem]:
        items: list[CategoryBreakdownItem] = []
        for c in raw_cats:
            amt = quantize_money(c["total_amount"])
            cnt = c["transaction_count"]
            pct = (
                ((amt / grand_total) * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                if grand_total > Decimal("0.00")
                else Decimal("0.00")
            )
            avg = (amt / cnt).quantize(TWO_PLACES, rounding=ROUND_HALF_UP) if cnt > 0 else Decimal("0.00")
            items.append(
                CategoryBreakdownItem(
                    category_id=c["category_id"],
                    category_name=c["category_name"],
                    category_color=c["category_color"],
                    total_amount=amt,
                    percentage=pct,
                    transaction_count=cnt,
                    average_amount=avg,
                )
            )
        return items

    def _enrich_accounts_breakdown(
        self, raw_accs: list[dict], grand_total: Decimal
    ) -> list[AccountBreakdownItem]:
        return [
            AccountBreakdownItem(
                account_id=a["account_id"],
                account_name=a["account_name"],
                account_type=a["account_type"],
                total_amount=quantize_money(a["total_amount"]),
                percentage=(
                    ((Decimal(a["total_amount"]) / grand_total) * Decimal("100")).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    )
                    if grand_total > Decimal("0.00")
                    else Decimal("0.00")
                ),
                transaction_count=a["transaction_count"],
            )
            for a in raw_accs
        ]

    def _enrich_sources(self, raw_sources: list[dict], grand_total: Decimal) -> list[SourceDistributionItem]:
        return [
            SourceDistributionItem(
                source=s["source"],
                label=SOURCE_LABELS.get(s["source"], s["source"].replace("_", " ").title()),
                total_amount=quantize_money(s["total_amount"]),
                percentage=(
                    ((Decimal(s["total_amount"]) / grand_total) * Decimal("100")).quantize(
                        TWO_PLACES, rounding=ROUND_HALF_UP
                    )
                    if grand_total > Decimal("0.00")
                    else Decimal("0.00")
                ),
                transaction_count=s["transaction_count"],
            )
            for s in raw_sources
        ]

    def _build_account_analytics_items(
        self,
        db: Session,
        user: User,
        bounds: PeriodBounds,
        verify_with_ledger: bool = True,
    ) -> tuple[list[AccountAnalyticsItem], list, Decimal, Decimal]:
        accounts = self.account_repo.list_by_user(db, user.id, include_archived=False)
        activity_map = self.analytics_repo.get_account_period_activity_map(
            db, user.id, bounds.start_date, bounds.end_date
        )
        total_assets = Decimal("0.00")
        total_liabilities = Decimal("0.00")
        items: list[AccountAnalyticsItem] = []

        for acc in accounts:
            balance = (
                self.ledger_repo.calculate_account_balance(db, acc.id, acc.account_type)
                if verify_with_ledger
                else acc.current_balance
            )
            balance = quantize_money(balance)
            is_liability = acc.account_type == "credit_card"
            if is_liability:
                total_liabilities += balance
            else:
                total_assets += balance

            act = activity_map.get(
                acc.id, {"income": Decimal("0.00"), "expenses": Decimal("0.00"), "count": 0}
            )
            p_inc = quantize_money(act["income"])
            p_exp = quantize_money(act["expenses"])
            items.append(
                AccountAnalyticsItem(
                    account_id=acc.id,
                    name=acc.name,
                    institution_name=acc.institution_name,
                    account_type=acc.account_type,
                    current_balance=balance,
                    is_liability=is_liability,
                    currency=acc.currency,
                    source=acc.source,
                    status=acc.status,
                    transaction_count=int(act["count"]),
                    period_income=p_inc,
                    period_expenses=p_exp,
                    net_transaction_activity=quantize_money(p_inc - p_exp),
                )
            )

        return items, accounts, quantize_money(total_assets), quantize_money(total_liabilities)

    def _reconstruct_balance_history(
        self,
        db: Session,
        user_id: uuid.UUID,
        bounds: PeriodBounds,
        account_id: uuid.UUID | None = None,
    ) -> tuple[list[BalanceTrendPoint], bool, str]:
        deltas = self.analytics_repo.get_ledger_balance_deltas_by_date(
            db, user_id, bounds.end_date, account_id=account_id
        )
        if not deltas:
            return (
                [],
                False,
                "No unreversed double-entry ledger history available for the selected range.",
            )

        # Accumulate debit/credit balance per entry_date
        running_assets = Decimal("0.00")
        running_liabilities = Decimal("0.00")
        daily_snapshots: dict[dt.date, tuple[Decimal, Decimal]] = {}

        for row in deltas:
            d = row["entry_date"]
            amt = Decimal(row["amount"])
            is_card = row["account_type"] == "credit_card"
            if is_card:
                running_liabilities += amt if row["entry_type"] == "credit" else -amt
            else:
                running_assets += amt if row["entry_type"] == "debit" else -amt
            daily_snapshots[d] = (quantize_money(running_assets), quantize_money(running_liabilities))

        points: list[BalanceTrendPoint] = []
        prior_dates = [d for d in daily_snapshots if d < bounds.start_date]
        if prior_dates:
            latest_prior = max(prior_dates)
            a_bal, l_bal = daily_snapshots[latest_prior]
            points.append(
                BalanceTrendPoint(
                    date=bounds.start_date,
                    label=bounds.start_date.strftime("%d %b"),
                    assets_balance=a_bal,
                    liabilities_balance=l_bal,
                    net_position=quantize_money(a_bal - l_bal),
                )
            )

        for d in sorted(daily_snapshots):
            if bounds.start_date <= d <= bounds.end_date:
                a_bal, l_bal = daily_snapshots[d]
                points.append(
                    BalanceTrendPoint(
                        date=d,
                        label=d.strftime("%d %b"),
                        assets_balance=a_bal,
                        liabilities_balance=l_bal,
                        net_position=quantize_money(a_bal - l_bal),
                    )
                )

        if not points:
            return (
                [],
                False,
                "No balance changes occurred on or before the selected end date.",
            )

        note = (
            "Reconstructed chronologically from unreversed double-entry ledger entries. "
            "Opening balances apply from their recorded entry date."
        )
        return points, True, note

    def _traceability(
        self,
        db: Session,
        user_id: uuid.UUID,
        bounds: PeriodBounds,
        included_count: int,
        formula: str,
        account_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> CalculationMetadata:
        ex_tr, ex_rev = self.analytics_repo.get_excluded_counts(
            db, user_id, bounds.start_date, bounds.end_date, account_id=account_id
        )
        return CalculationMetadata(
            formula=formula,
            included_transaction_count=included_count,
            excluded_transfer_count=ex_tr,
            excluded_reversed_count=ex_rev,
            currency="INR",
            notes=notes,
        )

    def get_analytics_dashboard(
        self,
        db: Session,
        user: User,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> AnalyticsDashboardResponse:
        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        prev_bounds = resolve_previous_period_bounds(bounds)

        account_items, accounts, total_assets, total_liabilities = self._build_account_analytics_items(
            db, user, bounds, verify_with_ledger=True
        )
        net_position = quantize_money(total_assets - total_liabilities)

        cur_totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date
        )
        prev_totals = self.analytics_repo.get_period_totals(
            db, user.id, prev_bounds.start_date, prev_bounds.end_date
        )

        cur_inc = quantize_money(cur_totals["income"])
        cur_exp = quantize_money(cur_totals["expenses"])
        cur_net, cur_rate = compute_savings_rate(cur_inc, cur_exp)

        prev_inc = quantize_money(prev_totals["income"])
        prev_exp = quantize_money(prev_totals["expenses"])
        prev_net, _ = compute_savings_rate(prev_inc, prev_exp)

        gran = choose_granularity(bounds.start_date, bounds.end_date)
        ie_series = self._build_time_series(db, user.id, bounds, gran)

        # Always supply a rolling 6-month monthly trend ending on today (IST) for dashboard context
        today = ist_today()
        m6_bounds = resolve_period_bounds("last_6_months", reference_today=today)
        monthly_trend = self._build_time_series(db, user.id, m6_bounds, "month")

        raw_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, "expense", bounds.start_date, bounds.end_date
        )
        spending_cats = self._enrich_categories(raw_cats, cur_exp)

        recent_txs, _ = self.transaction_repo.list_transactions(
            db=db,
            user_id=user.id,
            start_date=bounds.start_date if period != "all_time" else None,
            end_date=bounds.end_date if period != "all_time" else None,
            page=1,
            page_size=8,
            sort_by="date_desc",
        )
        recent_responses = [self.tx_service._to_response(tx) for tx in recent_txs]

        trace = self._traceability(
            db=db,
            user_id=user.id,
            bounds=bounds,
            included_count=int(cur_totals["total_count"]),
            formula="Net Position = Assets - Liabilities; Net Savings = Income - Expenses; Savings Rate = (Net Savings / Income) * 100",
            notes="Transfers and reversed journals are excluded from income/expense figures.",
        )

        return AnalyticsDashboardResponse(
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_financial_position=net_position,
            account_count=len(accounts),
            period_bounds=bounds,
            total_income=cur_inc,
            total_expenses=cur_exp,
            net_savings=cur_net,
            savings_rate_pct=cur_rate,
            income_comparison=compute_comparison_metric(cur_inc, prev_inc),
            expense_comparison=compute_comparison_metric(cur_exp, prev_exp),
            savings_comparison=compute_comparison_metric(cur_net, prev_net),
            income_vs_expense_series=ie_series,
            spending_by_category=spending_cats,
            monthly_spending_trend=monthly_trend,
            account_balances=account_items,
            accounts=[AccountResponse.model_validate(a) for a in accounts],
            recent_transactions=recent_responses,
            is_empty_state=(len(accounts) == 0 and int(cur_totals["total_count"]) == 0),
            traceability=trace,
        )

    def get_income_analytics(
        self,
        db: Session,
        user: User,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        granularity: str | None = None,
        account_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> IncomeAnalyticsResponse:
        if account_id:
            self._assert_owned_account(db, user, account_id)

        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        prev_bounds = resolve_previous_period_bounds(bounds)
        gran = choose_granularity(bounds.start_date, bounds.end_date, granularity)

        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date, account_id=account_id, source=source, transaction_type="income"
        )
        prev_totals = self.analytics_repo.get_period_totals(
            db, user.id, prev_bounds.start_date, prev_bounds.end_date, account_id=account_id, source=source, transaction_type="income"
        )
        total_income = quantize_money(totals["income"])
        prev_income = quantize_money(prev_totals["income"])

        by_cat = self._enrich_categories(
            self.analytics_repo.get_category_breakdown(
                db, user.id, "income", bounds.start_date, bounds.end_date, account_id=account_id, source=source
            ),
            total_income,
        )
        by_acc = self._enrich_accounts_breakdown(
            self.analytics_repo.get_account_breakdown(
                db, user.id, "income", bounds.start_date, bounds.end_date, source=source
            ),
            total_income,
        )
        by_src = self._enrich_sources(
            self.analytics_repo.get_source_distribution(
                db, user.id, "income", bounds.start_date, bounds.end_date, account_id=account_id
            ),
            total_income,
        )
        trend = self._build_time_series(
            db, user.id, bounds, gran, account_id=account_id, source=source
        )
        trace = self._traceability(
            db, user.id, bounds, int(totals["income_count"]),
            formula="Total Income = SUM(amount) WHERE transaction_type = 'income' AND transfer_id IS NULL",
            account_id=account_id,
        )
        return IncomeAnalyticsResponse(
            period_bounds=bounds,
            granularity=gran,
            total_income=total_income,
            transaction_count=int(totals["income_count"]),
            by_category=by_cat,
            by_account=by_acc,
            by_source=by_src,
            trend=trend,
            comparison=compute_comparison_metric(total_income, prev_income),
            traceability=trace,
        )

    def get_expense_analytics(
        self,
        db: Session,
        user: User,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        granularity: str | None = None,
        account_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> ExpenseAnalyticsResponse:
        if account_id:
            self._assert_owned_account(db, user, account_id)

        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        prev_bounds = resolve_previous_period_bounds(bounds)
        gran = choose_granularity(bounds.start_date, bounds.end_date, granularity)

        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date, account_id=account_id, source=source, transaction_type="expense"
        )
        prev_totals = self.analytics_repo.get_period_totals(
            db, user.id, prev_bounds.start_date, prev_bounds.end_date, account_id=account_id, source=source, transaction_type="expense"
        )
        total_expenses = quantize_money(totals["expenses"])
        prev_expenses = quantize_money(prev_totals["expenses"])

        divisor_days = max(1, bounds.elapsed_days if bounds.is_partial_period else bounds.days_in_period)
        avg_daily = (total_expenses / Decimal(divisor_days)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        avg_monthly = (
            (total_expenses / (Decimal(bounds.days_in_period) / Decimal("30.00"))).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            if bounds.days_in_period >= 28
            else None
        )

        by_cat = self._enrich_categories(
            self.analytics_repo.get_category_breakdown(
                db, user.id, "expense", bounds.start_date, bounds.end_date, account_id=account_id, source=source
            ),
            total_expenses,
        )
        by_acc = self._enrich_accounts_breakdown(
            self.analytics_repo.get_account_breakdown(
                db, user.id, "expense", bounds.start_date, bounds.end_date, source=source
            ),
            total_expenses,
        )
        by_src = self._enrich_sources(
            self.analytics_repo.get_source_distribution(
                db, user.id, "expense", bounds.start_date, bounds.end_date, account_id=account_id
            ),
            total_expenses,
        )
        trend = self._build_time_series(
            db, user.id, bounds, gran, account_id=account_id, source=source
        )
        largest = [
            self.tx_service._to_response(tx)
            for tx in self.analytics_repo.get_largest_transactions(
                db, user.id, "expense", bounds.start_date, bounds.end_date, account_id=account_id, limit=8
            )
        ]
        trace = self._traceability(
            db, user.id, bounds, int(totals["expense_count"]),
            formula="Total Expenses = SUM(amount) WHERE transaction_type = 'expense' AND transfer_id IS NULL (includes credit card purchases, excludes card repayments)",
            account_id=account_id,
        )
        return ExpenseAnalyticsResponse(
            period_bounds=bounds,
            granularity=gran,
            total_expenses=total_expenses,
            transaction_count=int(totals["expense_count"]),
            average_daily_spend=avg_daily,
            average_monthly_spend=avg_monthly,
            by_category=by_cat,
            by_account=by_acc,
            by_source=by_src,
            trend=trend,
            largest_expenses=largest,
            comparison=compute_comparison_metric(total_expenses, prev_expenses),
            traceability=trace,
        )

    def get_cashflow_analytics(
        self,
        db: Session,
        user: User,
        period: str = "last_6_months",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        granularity: str | None = None,
        account_id: uuid.UUID | None = None,
    ) -> CashFlowAnalyticsResponse:
        if account_id:
            self._assert_owned_account(db, user, account_id)

        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        gran = choose_granularity(bounds.start_date, bounds.end_date, granularity)
        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date, account_id=account_id
        )
        inc = quantize_money(totals["income"])
        exp = quantize_money(totals["expenses"])
        net, rate = compute_savings_rate(inc, exp)
        series = self._build_time_series(db, user.id, bounds, gran, account_id=account_id)
        trace = self._traceability(
            db, user.id, bounds, int(totals["total_count"]),
            formula="Net Cash Flow = Total Income - Total Expenses (excluding internal transfers & reversed journals)",
            account_id=account_id,
        )
        return CashFlowAnalyticsResponse(
            period_bounds=bounds,
            granularity=gran,
            total_income=inc,
            total_expenses=exp,
            net_cash_flow=net,
            savings_rate_pct=rate,
            series=series,
            traceability=trace,
        )

    def get_category_analytics(
        self,
        db: Session,
        user: User,
        category_type: str = "expense",
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        account_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> CategoryAnalyticsResponse:
        if category_type not in {"expense", "income"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="category_type must be 'expense' or 'income'.",
            )
        if account_id:
            self._assert_owned_account(db, user, account_id)

        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date,
            account_id=account_id, source=source, transaction_type=category_type,
        )
        grand = quantize_money(totals["income"] if category_type == "income" else totals["expenses"])
        cnt = int(totals["income_count"] if category_type == "income" else totals["expense_count"])
        raw_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, category_type, bounds.start_date, bounds.end_date,
            account_id=account_id, source=source,
        )
        trace = self._traceability(
            db, user.id, bounds, cnt,
            formula=f"Category Share % = (Category {category_type.title()} / Total {category_type.title()}) * 100",
            account_id=account_id,
        )
        return CategoryAnalyticsResponse(
            period_bounds=bounds,
            category_type=category_type,  # type: ignore[arg-type]
            total_amount=grand,
            transaction_count=cnt,
            items=self._enrich_categories(raw_cats, grand),
            traceability=trace,
        )

    def get_trend_analytics(
        self,
        db: Session,
        user: User,
        period: str = "last_6_months",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        granularity: str | None = None,
        account_id: uuid.UUID | None = None,
    ) -> TrendAnalyticsResponse:
        if account_id:
            self._assert_owned_account(db, user, account_id)

        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        gran = choose_granularity(bounds.start_date, bounds.end_date, granularity)
        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date, account_id=account_id
        )
        series = self._build_time_series(db, user.id, bounds, gran, account_id=account_id)

        # Top 4 expense category trends cleanly
        raw_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, "expense", bounds.start_date, bounds.end_date, account_id=account_id
        )[:4]
        top_cat_trends = []
        for cat in raw_cats:
            c_series = self._build_time_series(
                db, user.id, bounds, gran, account_id=account_id, category_id=cat["category_id"]
            )
            top_cat_trends.append(
                {
                    "category_id": str(cat["category_id"]) if cat["category_id"] else None,
                    "category_name": cat["category_name"],
                    "category_color": cat["category_color"],
                    "total_amount": str(quantize_money(cat["total_amount"])),
                    "points": [{"label": p.label, "amount": str(p.expenses)} for p in c_series],
                }
            )

        bal_points, bal_avail, bal_note = self._reconstruct_balance_history(
            db, user.id, bounds, account_id=account_id
        )
        trace = self._traceability(
            db, user.id, bounds, int(totals["total_count"]),
            formula="Historical trends aggregated by calendar bucket directly from FinancialTransaction & LedgerEntry",
            account_id=account_id,
        )
        return TrendAnalyticsResponse(
            period_bounds=bounds,
            granularity=gran,
            series=series,
            top_category_trends=top_cat_trends,
            balance_history=bal_points,
            balance_history_available=bal_avail,
            balance_history_note=bal_note,
            traceability=trace,
        )

    def get_period_comparison(
        self,
        db: Session,
        user: User,
        comparison_preset: str = "month_over_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        account_id: uuid.UUID | None = None,
    ) -> PeriodComparisonResponse:
        if account_id:
            self._assert_owned_account(db, user, account_id)

        preset_to_period = {
            "month_over_month": "this_month",
            "quarter_over_quarter": "this_quarter",
            "year_over_year": "this_year",
            "last_3_months": "last_3_months",
            "custom": "custom",
        }
        if comparison_preset not in preset_to_period:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported comparison preset.",
            )

        target_period = preset_to_period[comparison_preset]
        cur_bounds = self._resolve_bounds_for_user(db, user, target_period, start_date, end_date)
        prev_bounds = resolve_previous_period_bounds(cur_bounds)

        cur_t = self.analytics_repo.get_period_totals(
            db, user.id, cur_bounds.start_date, cur_bounds.end_date, account_id=account_id
        )
        prev_t = self.analytics_repo.get_period_totals(
            db, user.id, prev_bounds.start_date, prev_bounds.end_date, account_id=account_id
        )

        cur_inc, cur_exp = quantize_money(cur_t["income"]), quantize_money(cur_t["expenses"])
        prev_inc, prev_exp = quantize_money(prev_t["income"]), quantize_money(prev_t["expenses"])
        cur_net, cur_rate = compute_savings_rate(cur_inc, cur_exp)
        prev_net, prev_rate = compute_savings_rate(prev_inc, prev_exp)

        # Category comparisons across union of expense categories present in either period
        cur_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, "expense", cur_bounds.start_date, cur_bounds.end_date, account_id=account_id
        )
        prev_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, "expense", prev_bounds.start_date, prev_bounds.end_date, account_id=account_id
        )
        cat_map: dict[tuple[uuid.UUID | None, str], dict] = {}
        for row in cur_cats:
            key = (row["category_id"], row["category_name"])
            cat_map[key] = {
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "category_color": row["category_color"],
                "cur": row["total_amount"],
                "prev": Decimal("0.00"),
            }
        for row in prev_cats:
            key = (row["category_id"], row["category_name"])
            entry = cat_map.setdefault(
                key,
                {
                    "category_id": row["category_id"],
                    "category_name": row["category_name"],
                    "category_color": row["category_color"],
                    "cur": Decimal("0.00"),
                    "prev": Decimal("0.00"),
                },
            )
            entry["prev"] = row["total_amount"]

        cat_comparisons = [
            CategoryComparisonItem(
                category_id=v["category_id"],
                category_name=v["category_name"],
                category_color=v["category_color"],
                comparison=compute_comparison_metric(v["cur"], v["prev"]),
            )
            for v in sorted(
                cat_map.values(),
                key=lambda x: max(x["cur"], x["prev"]),
                reverse=True,
            )
        ]

        partial_warning = None
        if cur_bounds.is_partial_period and not prev_bounds.is_partial_period:
            partial_warning = (
                f"Partial period comparison: '{cur_bounds.label}' has {cur_bounds.elapsed_days} of "
                f"{cur_bounds.days_in_period} days elapsed compared against full '{prev_bounds.label}' "
                f"({prev_bounds.days_in_period} days)."
            )

        return PeriodComparisonResponse(
            comparison_preset=comparison_preset,
            current_period=cur_bounds,
            previous_period=prev_bounds,
            income=compute_comparison_metric(cur_inc, prev_inc),
            expenses=compute_comparison_metric(cur_exp, prev_exp),
            net_savings=compute_comparison_metric(cur_net, prev_net),
            savings_rate_current=cur_rate,
            savings_rate_previous=prev_rate,
            category_comparisons=cat_comparisons,
            partial_period_warning=partial_warning,
        )

    def get_accounts_analytics(
        self,
        db: Session,
        user: User,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ) -> AccountAnalyticsListResponse:
        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        items, _, total_assets, total_liabilities = self._build_account_analytics_items(
            db, user, bounds, verify_with_ledger=True
        )
        return AccountAnalyticsListResponse(
            period_bounds=bounds,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            net_financial_position=quantize_money(total_assets - total_liabilities),
            accounts=items,
        )

    def get_account_detail_analytics(
        self,
        db: Session,
        user: User,
        account_id: uuid.UUID,
        period: str = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        granularity: str | None = None,
    ) -> AccountAnalyticsDetailResponse:
        acc = self._assert_owned_account(db, user, account_id)
        bounds = self._resolve_bounds_for_user(db, user, period, start_date, end_date)
        gran = choose_granularity(bounds.start_date, bounds.end_date, granularity)

        balance = quantize_money(
            self.ledger_repo.calculate_account_balance(db, acc.id, acc.account_type)
        )
        totals = self.analytics_repo.get_period_totals(
            db, user.id, bounds.start_date, bounds.end_date, account_id=acc.id
        )
        p_inc = quantize_money(totals["income"])
        p_exp = quantize_money(totals["expenses"])
        acc_item = AccountAnalyticsItem(
            account_id=acc.id,
            name=acc.name,
            institution_name=acc.institution_name,
            account_type=acc.account_type,
            current_balance=balance,
            is_liability=acc.account_type == "credit_card",
            currency=acc.currency,
            source=acc.source,
            status=acc.status,
            transaction_count=int(totals["total_count"]),
            period_income=p_inc,
            period_expenses=p_exp,
            net_transaction_activity=quantize_money(p_inc - p_exp),
        )

        trend = self._build_time_series(db, user.id, bounds, gran, account_id=acc.id)
        raw_cats = self.analytics_repo.get_category_breakdown(
            db, user.id, "expense", bounds.start_date, bounds.end_date, account_id=acc.id
        )
        cat_dist = self._enrich_categories(raw_cats, p_exp)
        txs = self.analytics_repo.list_report_transactions(
            db, user.id, bounds.start_date, bounds.end_date,
            account_id=acc.id, include_transfers=True, limit=50,
        )
        recent = [self.tx_service._to_response(t) for t in txs]
        bal_hist, _, bal_note = self._reconstruct_balance_history(
            db, user.id, bounds, account_id=acc.id
        )
        trace = self._traceability(
            db, user.id, bounds, int(totals["total_count"]),
            formula="Current balance derived from LedgerRepository unreversed entries; period activity excludes transfers.",
            account_id=acc.id,
        )
        return AccountAnalyticsDetailResponse(
            period_bounds=bounds,
            granularity=gran,
            account=acc_item,
            trend=trend,
            category_distribution=cat_dist,
            recent_transactions=recent,
            balance_history=bal_hist,
            balance_history_note=bal_note,
            traceability=trace,
        )
