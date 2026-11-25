import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.intelligence import (
    AiModelMetadataResponse,
    AiProcessingJobResponse,
    AnomalyReviewRequest,
    CategorizationFeedbackResponse,
    CategorizeTransactionsRequest,
    FinancialInsightListResponse,
    FinancialInsightResponse,
    InsightReviewRequest,
    IntelligenceOverviewResponse,
    IntelligenceRunRequest,
    MerchantIdentityResponse,
    MerchantListResponse,
    MerchantUpdateRequest,
    RecurringCandidateDecisionRequest,
    RecurringCandidateListResponse,
    RecurringPaymentCandidateResponse,
    SpendingAnomalyListResponse,
    SpendingAnomalyResponse,
    SpendingPatternsResponse,
    TransactionCategorizationListResponse,
    TransactionCategorizationOverrideRequest,
    TransactionCategorizationResponse,
)
from app.services.ai.intelligence_service import IntelligenceService

router = APIRouter(prefix="/intelligence", tags=["AI Expense Intelligence"])
intel_service = IntelligenceService()


def _enforce_ai_rate_limit(user_id: uuid.UUID, op: str, max_requests: int = 20) -> None:
    allowed = rate_limiter.is_allowed(
        f"ai:{op}:{user_id}",
        max_requests=max_requests,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI analysis rate limit exceeded. Please wait a minute and retry.",
        )


@router.get("/overview", response_model=IntelligenceOverviewResponse)
def get_intelligence_overview(
    lookback_days: int = Query(default=180, ge=30, le=1825),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.get_overview(db, current_user, lookback_days=lookback_days)


@router.post("/run", response_model=AiProcessingJobResponse)
def run_full_intelligence(
    payload: IntelligenceRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_ai_rate_limit(current_user.id, "run", max_requests=15)
    if payload.async_job:
        job = intel_service.enqueue_intelligence_job(db, current_user)
        return AiProcessingJobResponse.model_validate(job)
    job = intel_service.execute_full_pipeline_for_user(db, current_user.id, payload)
    return AiProcessingJobResponse.model_validate(job)


@router.post("/categorize")
def run_categorization(
    payload: CategorizeTransactionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_ai_rate_limit(current_user.id, "categorize", max_requests=25)
    return intel_service.run_categorization(db, current_user, payload)


@router.get("/categorizations", response_model=TransactionCategorizationListResponse)
def list_categorizations(
    review_status: str | None = Query(default=None),
    method: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_categorizations(
        db,
        current_user,
        review_status=review_status,
        method=method,
        search=search,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/categorizations/{transaction_id}/override",
    response_model=TransactionCategorizationResponse,
)
def override_categorization(
    transaction_id: uuid.UUID,
    payload: TransactionCategorizationOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return intel_service.override_transaction_categorization(
        db, current_user, transaction_id, payload
    )


@router.get("/feedback", response_model=list[CategorizationFeedbackResponse])
def list_categorization_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_feedback(db, current_user)


@router.post("/ml/train", response_model=AiModelMetadataResponse)
def train_ml_classifier(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_ai_rate_limit(current_user.id, "ml_train", max_requests=12)
    return intel_service.train_classifier(db, current_user)


@router.get("/ml/status", response_model=AiModelMetadataResponse | None)
def get_ml_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.get_model_status(db, current_user)


@router.get("/merchants", response_model=MerchantListResponse)
def list_merchants(
    search: str | None = Query(default=None, max_length=120),
    confirmed_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1, le=500),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_merchants(
        db,
        current_user,
        search=search,
        confirmed_only=confirmed_only,
        page=page,
        page_size=page_size,
    )


@router.patch("/merchants/{merchant_id}", response_model=MerchantIdentityResponse)
def update_merchant(
    merchant_id: uuid.UUID,
    payload: MerchantUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return intel_service.update_merchant(db, current_user, merchant_id, payload)


@router.get("/recurring-candidates", response_model=RecurringCandidateListResponse)
def list_recurring_candidates(
    review_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_recurring_candidates(db, current_user, review_status=review_status)


@router.post(
    "/recurring-candidates/{candidate_id}/decision",
    response_model=RecurringPaymentCandidateResponse,
)
def decide_recurring_candidate(
    candidate_id: uuid.UUID,
    payload: RecurringCandidateDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return intel_service.decide_recurring_candidate(db, current_user, candidate_id, payload)


@router.get("/patterns", response_model=SpendingPatternsResponse)
def get_spending_patterns(
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.get_spending_patterns(
        db, current_user, date_from=date_from, date_to=date_to
    )


@router.get("/anomalies", response_model=SpendingAnomalyListResponse)
def list_anomalies(
    review_status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_anomalies(
        db, current_user, review_status=review_status, severity=severity
    )


@router.post("/anomalies/{anomaly_id}/review", response_model=SpendingAnomalyResponse)
def review_anomaly(
    anomaly_id: uuid.UUID,
    payload: AnomalyReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return intel_service.review_anomaly(db, current_user, anomaly_id, payload)


@router.get("/insights", response_model=FinancialInsightListResponse)
def list_insights(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_insights(db, current_user, status_filter=status_filter)


@router.post("/insights/{insight_id}/review", response_model=FinancialInsightResponse)
def review_insight(
    insight_id: uuid.UUID,
    payload: InsightReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return intel_service.review_insight(db, current_user, insight_id, payload)


@router.get("/jobs", response_model=list[AiProcessingJobResponse])
def list_ai_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return intel_service.list_jobs(db, current_user)
