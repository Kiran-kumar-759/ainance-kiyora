import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics.reports import (
    FinancialReportResponse,
    ReportListResponse,
    ReportTypeLiteral,
)
from app.services.analytics.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Financial Reports"])
report_service = ReportService()


def _run_report(
    report_type: ReportTypeLiteral,
    period: str | None,
    start_date: dt.date | None,
    end_date: dt.date | None,
    account_id: uuid.UUID | None,
    transaction_type: str | None,
    category_id: uuid.UUID | None,
    source: str | None,
    db: Session,
    current_user: User,
) -> FinancialReportResponse:
    return report_service.generate_report(
        db=db,
        user=current_user,
        report_type=report_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        source=source,
    )


@router.get("", response_model=ReportListResponse, summary="List available financial report types")
def list_reports(current_user: User = Depends(get_current_user)):
    return report_service.list_definitions()


@router.get("/summary", response_model=FinancialReportResponse, summary="Generate monthly financial summary report")
def get_summary_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "monthly_summary", period, start_date, end_date, account_id, transaction_type, category_id, source, db, current_user
    )


@router.get("/income", response_model=FinancialReportResponse, summary="Generate income report")
def get_income_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "income_report", period, start_date, end_date, account_id, "income", category_id, source, db, current_user
    )


@router.get("/expenses", response_model=FinancialReportResponse, summary="Generate expense report")
def get_expense_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "expense_report", period, start_date, end_date, account_id, "expense", category_id, source, db, current_user
    )


@router.get("/categories", response_model=FinancialReportResponse, summary="Generate category spending report")
def get_categories_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query("expense"),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "category_spending", period, start_date, end_date, account_id, transaction_type, category_id, source, db, current_user
    )


@router.get("/accounts", response_model=FinancialReportResponse, summary="Generate account activity report")
def get_accounts_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "account_activity", period, start_date, end_date, account_id, transaction_type, category_id, source, db, current_user
    )


@router.get("/cashflow", response_model=FinancialReportResponse, summary="Generate cash-flow report")
def get_cashflow_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "cash_flow", period, start_date, end_date, account_id, transaction_type, category_id, source, db, current_user
    )


@router.get("/savings", response_model=FinancialReportResponse, summary="Generate savings report")
def get_savings_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "savings_report", period, start_date, end_date, account_id, None, None, source, db, current_user
    )


@router.get("/transactions", response_model=FinancialReportResponse, summary="Generate transaction summary report")
def get_transactions_report(
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _run_report(
        "transaction_summary", period, start_date, end_date, account_id, transaction_type, category_id, source, db, current_user
    )


@router.get("/export/csv", summary="Export filtered financial report as UTF-8 CSV")
def export_report_csv(
    report_type: ReportTypeLiteral = Query("monthly_summary"),
    period: str | None = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    transaction_type: str | None = Query(None),
    category_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename, csv_content = report_service.export_report_csv(
        db=db,
        user=current_user,
        report_type=report_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        transaction_type=transaction_type,
        category_id=category_id,
        source=source,
    )
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
