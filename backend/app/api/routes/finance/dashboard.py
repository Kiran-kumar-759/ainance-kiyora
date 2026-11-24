from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.finance.dashboard import FinancialDashboardResponse
from app.services.finance.dashboard_service import DashboardService

router = APIRouter(prefix="/finance/dashboard", tags=["Financial Dashboard"])
dashboard_service = DashboardService()


@router.get(
    "", response_model=FinancialDashboardResponse, summary="Get financial dashboard summary"
)
def get_dashboard(
    period: str = Query("this_month", description="this_month, last_month, this_year, all_time"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns high-level financial summary including total assets, credit card debt,
    net financial position, period income and expenses, and recent transactions.
    """
    return dashboard_service.get_dashboard_summary(db, current_user, period=period)
