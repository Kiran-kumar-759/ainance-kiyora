import csv
import datetime as dt
import io
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.analytics.analytics_repository import AnalyticsRepository
from app.repositories.finance.account_repository import AccountRepository
from app.repositories.finance.category_repository import CategoryRepository
from app.schemas.analytics.reports import (
    FinancialReportResponse,
    ReportDefinition,
    ReportFilterMetadata,
    ReportListResponse,
    ReportSummaryMetric,
    ReportTypeLiteral,
)
from app.services.analytics.analytics_service import AnalyticsService
from app.services.analytics.period_utils import (
    choose_granularity,
    compute_savings_rate,
    ist_now,
    quantize_money,
    resolve_period_bounds,
)
from app.services.finance.transaction_service import TransactionService

REPORT_DEFINITIONS: list[ReportDefinition] = [
    ReportDefinition(
        id="monthly_summary",
        title="Monthly Financial Summary",
        description="Complete overview of income, expenses, net savings, category splits, and ledger transactions.",
    ),
    ReportDefinition(
        id="income_report",
        title="Income Report",
        description="Detailed breakdown of all earnings by category, account, and ingestion source.",
    ),
    ReportDefinition(
        id="expense_report",
        title="Expense Report",
        description="Spending breakdown across accounts, payment modes, and categories (excluding transfers).",
    ),
    ReportDefinition(
        id="category_spending",
        title="Category-Wise Spending Report",
        description="Ranked expense categories with spend totals, shares, averages, and transaction counts.",
    ),
    ReportDefinition(
        id="account_activity",
        title="Account-Wise Activity Report",
        description="Account activity summary with inflows, outflows, and complete transaction ledger.",
    ),
    ReportDefinition(
        id="cash_flow",
        title="Cash-Flow Report",
        description="Time-series cash inflows, outflows, and net surplus across selected calendar intervals.",
    ),
    ReportDefinition(
        id="savings_report",
        title="Savings Report",
        description="Net savings capacity and savings rate tracking over the selected date window.",
    ),
    ReportDefinition(
        id="transaction_summary",
        title="Transaction Summary Report",
        description="Auditable transaction statement respecting account, type, category, and source filters.",
    ),
]

REPORT_MAP: dict[str, ReportDefinition] = {r.id: r for r in REPORT_DEFINITIONS}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: object) -> str:
    """
    Neutralizes spreadsheet formula injection (CSV/DDE injection) cleanly.
    Any string starting with =, +, -, @, tab, or CR (after optional leading whitespace)
    is prefixed with a single quote so spreadsheet clients treat it strictly as text.
    """
    if value is None:
        return ""
    text = str(value)
    stripped = text.lstrip(" ")
    if stripped and stripped[0] in FORMULA_PREFIXES:
        return f"'{text}"
    return text


def _format_inr_display(amount: Decimal) -> str:
    return f"₹{quantize_money(amount):,.2f}"


class ReportService:
    """Service generating structured financial reports and formula-safe CSV exports."""

    def __init__(self):
        self.analytics_repo = AnalyticsRepository()
        self.analytics_service = AnalyticsService()
        self.account_repo = AccountRepository()
        self.category_repo = CategoryRepository()
        self.tx_service = TransactionService()

    def list_definitions(self) -> ReportListResponse:
        return ReportListResponse(reports=REPORT_DEFINITIONS)

    def _resolve_report_range(
        self,
        db: Session,
        user: User,
        period: str | None,
        start_date: dt.date | None,
        end_date: dt.date | None,
    ) -> tuple[dt.date, dt.date]:
        if start_date is not None and end_date is not None:
            bounds = resolve_period_bounds("custom", start_date=start_date, end_date=end_date)
            return bounds.start_date, bounds.end_date
        if start_date is not None or end_date is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date must be provided together.",
            )
        bounds = self.analytics_service._resolve_bounds_for_user(
            db, user, period or "this_month"
        )
        return bounds.start_date, bounds.end_date

    def generate_report(
        self,
        db: Session,
        user: User,
        report_type: ReportTypeLiteral = "monthly_summary",
        period: str | None = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        account_id: uuid.UUID | None = None,
        transaction_type: str | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> FinancialReportResponse:
        if report_type not in REPORT_MAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown report_type '{report_type}'.",
            )

        acc_name = None
        if account_id is not None:
            acc = self.analytics_service._assert_owned_account(db, user, account_id)
            acc_name = acc.name

        cat_name = None
        if category_id is not None:
            cat = self.analytics_service._assert_owned_category(db, user, category_id)
            cat_name = cat.name

        if transaction_type and transaction_type not in {"income", "expense", "transfer"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="transaction_type must be 'income', 'expense', or 'transfer'.",
            )

        # Infer default transaction_type focus for dedicated income/expense reports unless overridden
        effective_tx_type = transaction_type
        if effective_tx_type is None:
            if report_type == "income_report":
                effective_tx_type = "income"
            elif report_type in {"expense_report", "category_spending"}:
                effective_tx_type = "expense"

        s_date, e_date = self._resolve_report_range(db, user, period, start_date, end_date)
        bounds = resolve_period_bounds("custom", start_date=s_date, end_date=e_date)

        totals = self.analytics_repo.get_period_totals(
            db,
            user.id,
            s_date,
            e_date,
            account_id=account_id,
            category_id=category_id,
            source=source,
            transaction_type=effective_tx_type if effective_tx_type in {"income", "expense"} else None,
        )
        total_income = quantize_money(totals["income"])
        total_expenses = quantize_money(totals["expenses"])
        net_savings, savings_rate = compute_savings_rate(total_income, total_expenses)

        cat_type = "income" if effective_tx_type == "income" else "expense"
        cat_grand = total_income if cat_type == "income" else total_expenses
        raw_cats = self.analytics_repo.get_category_breakdown(
            db,
            user.id,
            cat_type,
            s_date,
            e_date,
            account_id=account_id,
            source=source,
            category_id=category_id,
        )
        category_breakdown = self.analytics_service._enrich_categories(raw_cats, cat_grand)

        raw_accs = self.analytics_repo.get_account_breakdown(
            db,
            user.id,
            cat_type,
            s_date,
            e_date,
            category_id=category_id,
            source=source,
        )
        if account_id is not None:
            raw_accs = [a for a in raw_accs if a["account_id"] == account_id]
        account_breakdown = self.analytics_service._enrich_accounts_breakdown(raw_accs, cat_grand)

        gran = choose_granularity(s_date, e_date)
        cashflow_series = self.analytics_service._build_time_series(
            db, user.id, bounds, gran, account_id=account_id, category_id=category_id, source=source
        )

        include_transfers = (
            report_type in {"account_activity", "transaction_summary"}
            or effective_tx_type == "transfer"
        )
        tx_rows = self.analytics_repo.list_report_transactions(
            db=db,
            user_id=user.id,
            start_date=s_date,
            end_date=e_date,
            account_id=account_id,
            transaction_type=effective_tx_type,
            category_id=category_id,
            source=source,
            include_transfers=include_transfers,
            limit=5000,
        )
        tx_responses = [self.tx_service._to_response(t) for t in tx_rows]

        summary_metrics = [
            ReportSummaryMetric(
                label="Total Income",
                value=_format_inr_display(total_income),
                raw_decimal=total_income,
                highlight="positive",
            ),
            ReportSummaryMetric(
                label="Total Expenses",
                value=_format_inr_display(total_expenses),
                raw_decimal=total_expenses,
                highlight="negative",
            ),
            ReportSummaryMetric(
                label="Net Savings",
                value=_format_inr_display(net_savings),
                raw_decimal=net_savings,
                highlight="positive" if net_savings >= Decimal("0.00") else "negative",
            ),
            ReportSummaryMetric(
                label="Savings Rate",
                value=f"{savings_rate}%" if savings_rate is not None else "N/A (Zero Income)",
                raw_decimal=savings_rate,
                highlight="neutral",
            ),
        ]

        trace = self.analytics_service._traceability(
            db=db,
            user_id=user.id,
            bounds=bounds,
            included_count=int(totals["total_count"]),
            formula="Report figures derived from FinancialTransaction excluding transfers and reversed ledger entries.",
            account_id=account_id,
        )

        metadata = ReportFilterMetadata(
            report_type=report_type,
            title=REPORT_MAP[report_type].title,
            start_date=s_date,
            end_date=e_date,
            account_id=account_id,
            account_name=acc_name,
            transaction_type=effective_tx_type,
            category_id=category_id,
            category_name=cat_name,
            source=source,
            generated_at=ist_now(),
            currency="INR",
            timezone="Asia/Kolkata",
        )

        return FinancialReportResponse(
            metadata=metadata,
            summary_metrics=summary_metrics,
            category_breakdown=category_breakdown,
            account_breakdown=account_breakdown,
            cashflow_series=cashflow_series,
            transactions=tx_responses,
            total_transactions=len(tx_responses),
            traceability=trace,
        )

    def export_report_csv(
        self,
        db: Session,
        user: User,
        report_type: ReportTypeLiteral = "monthly_summary",
        period: str | None = "this_month",
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
        account_id: uuid.UUID | None = None,
        transaction_type: str | None = None,
        category_id: uuid.UUID | None = None,
        source: str | None = None,
    ) -> tuple[str, str]:
        report = self.generate_report(
            db=db,
            user=user,
            report_type=report_type,
            period=period,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            transaction_type=transaction_type,
            category_id=category_id,
            source=source,
        )

        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\r\n")

        meta = report.metadata
        writer.writerow(["Report Title", sanitize_csv_cell(meta.title)])
        writer.writerow(
            [
                "Period",
                f"{meta.start_date.strftime('%d/%m/%Y')} to {meta.end_date.strftime('%d/%m/%Y')}",
            ]
        )
        writer.writerow(["Generated At (IST)", meta.generated_at.strftime("%d/%m/%Y %H:%M:%S")])
        writer.writerow(["Currency", meta.currency])
        if meta.account_name:
            writer.writerow(["Account Filter", sanitize_csv_cell(meta.account_name)])
        if meta.category_name:
            writer.writerow(["Category Filter", sanitize_csv_cell(meta.category_name)])
        if meta.transaction_type:
            writer.writerow(["Type Filter", sanitize_csv_cell(meta.transaction_type)])
        if meta.source:
            writer.writerow(["Source Filter", sanitize_csv_cell(meta.source)])
        writer.writerow([])

        # Summary block
        writer.writerow(["Summary Metric", "Amount / Value (INR)"])
        for m in report.summary_metrics:
            val_str = f"{m.raw_decimal:.2f}" if m.raw_decimal is not None else m.value
            writer.writerow([sanitize_csv_cell(m.label), sanitize_csv_cell(val_str)])
        writer.writerow([])

        # Category Breakdown
        if report.category_breakdown:
            writer.writerow(["Category Breakdown", "Total (INR)", "Share %", "Transaction Count"])
            for c in report.category_breakdown:
                writer.writerow(
                    [
                        sanitize_csv_cell(c.category_name),
                        f"{c.total_amount:.2f}",
                        f"{c.percentage:.2f}",
                        str(c.transaction_count),
                    ]
                )
            writer.writerow([])

        # Transaction Records
        writer.writerow(
            [
                "Date (DD/MM/YYYY)",
                "Type",
                "Description",
                "Merchant / Payee",
                "Category",
                "Account",
                "Source",
                "Reference",
                "Amount (INR)",
                "Currency",
            ]
        )
        for tx in report.transactions:
            writer.writerow(
                [
                    tx.transaction_date.strftime("%d/%m/%Y"),
                    sanitize_csv_cell(tx.transaction_type),
                    sanitize_csv_cell(tx.description),
                    sanitize_csv_cell(tx.merchant_payee or ""),
                    sanitize_csv_cell(tx.category_name or "Uncategorized"),
                    sanitize_csv_cell(tx.account_name or ""),
                    sanitize_csv_cell(tx.source),
                    sanitize_csv_cell(tx.external_reference or ""),
                    f"{Decimal(tx.amount):.2f}",
                    sanitize_csv_cell(tx.currency),
                ]
            )

        filename = f"pfm_{meta.report_type}_{meta.start_date.strftime('%Y%m%d')}_{meta.end_date.strftime('%Y%m%d')}.csv"
        return filename, buf.getvalue()
