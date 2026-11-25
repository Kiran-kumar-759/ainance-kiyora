import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.forecasting import (
    AccountBalanceForecastItem,
    CashflowForecastResponse,
    CategoryForecastItem,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    ForecastEvaluationResponse,
    ForecastExplanationItem,
    ForecastingOverviewResponse,
    ForecastRecordResponse,
    ForecastScenarioRequest,
    ForecastScenarioResponse,
    GenerateForecastRequest,
    IncomeForecastResponse,
    SavingsForecastResponse,
)
from app.schemas.intelligence import AiProcessingJobResponse
from app.services.forecasting.forecast_service import ForecastService

router = APIRouter(prefix="/forecasting", tags=["Financial Forecasting & Predictive Analytics"])
forecast_service = ForecastService()


def _enforce_forecast_rate_limit(user_id: uuid.UUID, op: str, max_requests: int = 20) -> None:
    allowed = rate_limiter.is_allowed(
        f"forecast:{op}:{user_id}",
        max_requests=max_requests,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Forecasting rate limit exceeded. Please wait a minute and retry.",
        )


@router.get("/overview", response_model=ForecastingOverviewResponse)
def get_forecast_overview(
    horizon_days: int = Query(default=30, ge=7, le=365),
    low_balance_threshold: Decimal = Query(default=Decimal("5000.00"), ge=Decimal("0.00")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(
        db,
        current_user,
        horizon_days=horizon_days,
        low_balance_threshold=low_balance_threshold,
    )


@router.get("/cashflow", response_model=CashflowForecastResponse)
def get_cashflow_forecast(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).cashflow


@router.get("/expenses", response_model=ExpenseForecastResponse)
def get_expense_forecast(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).expenses


@router.get("/income", response_model=IncomeForecastResponse)
def get_income_forecast(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).income


@router.get("/categories", response_model=list[CategoryForecastItem])
def get_category_forecasts(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).categories


@router.get("/balances", response_model=list[AccountBalanceForecastItem])
def get_balance_forecasts(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).balances


@router.get("/commitments", response_model=list[CommitmentForecastItem])
def get_commitment_forecasts(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).commitments


@router.get("/savings", response_model=SavingsForecastResponse)
def get_savings_forecast(
    horizon_days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_overview(db, current_user, horizon_days=horizon_days).savings


@router.post("/generate")
def generate_forecast(
    payload: GenerateForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_forecast_rate_limit(current_user.id, "generate", max_requests=20)
    if payload.async_job:
        job = forecast_service.enqueue_forecast_job(db, current_user)
        return AiProcessingJobResponse.model_validate(job)
    return forecast_service.generate_forecast_for_user(db, current_user.id, payload)


@router.get("/history", response_model=list[ForecastRecordResponse])
def list_forecast_history(
    horizon_days: int | None = Query(default=None, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.list_history(db, current_user, horizon_days=horizon_days)


@router.post("/scenarios", response_model=ForecastScenarioResponse)
def create_or_simulate_scenario(
    payload: ForecastScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_forecast_rate_limit(current_user.id, "scenario", max_requests=30)
    return forecast_service.run_scenario(db, current_user, payload)


@router.get("/scenarios", response_model=list[ForecastScenarioResponse])
def list_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.list_scenarios(db, current_user)


@router.get("/scenarios/{scenario_id}", response_model=ForecastScenarioResponse)
def get_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_scenario(db, current_user, scenario_id)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    forecast_service.delete_scenario(db, current_user, scenario_id)


@router.get("/accuracy", response_model=ForecastEvaluationResponse)
def evaluate_forecast_accuracy(
    horizon_days: int = Query(default=30, ge=14, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _enforce_forecast_rate_limit(current_user.id, "accuracy", max_requests=15)
    return forecast_service.evaluate_accuracy(db, current_user, horizon_days=horizon_days)


@router.get("/evaluation/history", response_model=list[ForecastEvaluationResponse])
def list_evaluation_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.list_evaluations(db, current_user)


@router.get("/{forecast_id}", response_model=ForecastingOverviewResponse)
def get_forecast_by_id(
    forecast_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_forecast_detail(db, current_user, forecast_id)


@router.get("/{forecast_id}/explanation", response_model=list[ForecastExplanationItem])
def get_forecast_explanation(
    forecast_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return forecast_service.get_forecast_explanations(db, current_user, forecast_id)
