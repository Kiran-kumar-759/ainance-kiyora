import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics.analytics import (
    AccountAnalyticsDetailResponse,
    AccountAnalyticsListResponse,
    CashFlowAnalyticsResponse,
    CategoryAnalyticsResponse,
    ExpenseAnalyticsResponse,
    IncomeAnalyticsResponse,
    PeriodComparisonResponse,
    TrendAnalyticsResponse,
)
from app.schemas.analytics.dashboard import AnalyticsDashboardResponse
from app.services.analytics.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Financial Analytics"])
analytics_service = AnalyticsService()


@router.get("/dashboard", response_model=AnalyticsDashboardResponse, summary="Get comprehensive analytics dashboard")
def get_analytics_dashboard(
    period: str = Query(
        "this_month",
        description="this_week, this_month, last_month, last_3_months, last_6_months, this_quarter, last_quarter, this_year, last_year, all_time, custom",
    ),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    enforce_onboarding: bool = Query(
        False,
        description="When true, rejects access with 403 until user onboarding is completed",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if enforce_onboarding and not current_user.onboarding_completed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Onboarding must be completed before accessing the dashboard.",
        )
    return analytics_service.get_analytics_dashboard(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/income", response_model=IncomeAnalyticsResponse, summary="Get period income analytics")
def get_income_analytics(
    period: str = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    granularity: str | None = Query(None, description="daily, weekly, monthly, quarterly"),
    account_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_income_analytics(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        account_id=account_id,
        source=source,
    )


@router.get("/expenses", response_model=ExpenseAnalyticsResponse, summary="Get period expense analytics")
def get_expense_analytics(
    period: str = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    granularity: str | None = Query(None, description="daily, weekly, monthly, quarterly"),
    account_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_expense_analytics(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        account_id=account_id,
        source=source,
    )


@router.get("/cashflow", response_model=CashFlowAnalyticsResponse, summary="Get cash-flow analytics")
def get_cashflow_analytics(
    period: str = Query("last_6_months"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    granularity: str | None = Query(None, description="daily, weekly, monthly, quarterly"),
    account_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_cashflow_analytics(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        account_id=account_id,
    )


@router.get("/categories", response_model=CategoryAnalyticsResponse, summary="Get category spending or income distribution")
def get_category_analytics(
    category_type: str = Query("expense", description="expense or income"),
    period: str = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_category_analytics(
        db=db,
        user=current_user,
        category_type=category_type,
        period=period,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        source=source,
    )


@router.get("/trends", response_model=TrendAnalyticsResponse, summary="Get historical income, expense, category, and balance trends")
def get_trend_analytics(
    period: str = Query("last_6_months"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    granularity: str | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_trend_analytics(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        account_id=account_id,
    )


@router.get("/comparisons", response_model=PeriodComparisonResponse, summary="Compare current financial period against previous period")
def get_period_comparison(
    comparison_preset: str = Query(
        "month_over_month",
        description="month_over_month, quarter_over_quarter, year_over_year, last_3_months, custom",
    ),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    account_id: uuid.UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_period_comparison(
        db=db,
        user=current_user,
        comparison_preset=comparison_preset,
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
    )


@router.get("/accounts", response_model=AccountAnalyticsListResponse, summary="Get account-wise analytics summary")
def get_accounts_analytics(
    period: str = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_accounts_analytics(
        db=db,
        user=current_user,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/accounts/{account_id}", response_model=AccountAnalyticsDetailResponse, summary="Get detailed analytics for one financial account")
def get_account_detail_analytics(
    account_id: uuid.UUID,
    period: str = Query("this_month"),
    start_date: dt.date | None = Query(None),
    end_date: dt.date | None = Query(None),
    granularity: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return analytics_service.get_account_detail_analytics(
        db=db,
        user=current_user,
        account_id=account_id,
        period=period,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )
