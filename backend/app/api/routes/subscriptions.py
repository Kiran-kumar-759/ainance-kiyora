import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.subscriptions import (
    SubscriptionAnalyticsResponse,
    SubscriptionCancelRequest,
    SubscriptionCandidateActionRequest,
    SubscriptionCandidateResponse,
    SubscriptionCreateRequest,
    SubscriptionListResponse,
    SubscriptionOverviewResponse,
    SubscriptionPaymentCreateRequest,
    SubscriptionPaymentLinkRequest,
    SubscriptionPaymentListResponse,
    SubscriptionPaymentReverseRequest,
    SubscriptionPriceChangeRequest,
    SubscriptionReminderUpdateRequest,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)
from app.services.subscriptions.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["OTT & Subscriptions"])
sub_service = SubscriptionService()


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new OTT or recurring subscription",
)
def create_subscription(
    req: SubscriptionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.create_subscription(db, current_user, req)


@router.get("", response_model=SubscriptionListResponse, summary="List subscriptions with filters")
def list_subscriptions(
    status_filter: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("next_renewal_asc"),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.list_subscriptions(
        db,
        current_user,
        status_filter=status_filter,
        category=category,
        search=search,
        sort_by=sort_by,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


@router.get("/overview", response_model=SubscriptionOverviewResponse)
def get_subscription_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.get_overview(db, current_user)


@router.get("/analytics", response_model=SubscriptionAnalyticsResponse)
def get_subscription_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.get_analytics(db, current_user)


@router.get("/payments", response_model=SubscriptionPaymentListResponse)
def list_all_subscription_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.list_payments(db, current_user)


@router.get("/candidates", response_model=list[SubscriptionCandidateResponse])
def list_subscription_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.list_candidates(db, current_user)


@router.post("/candidates/decision")
def decide_subscription_candidate(
    req: SubscriptionCandidateActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.handle_candidate_decision(db, current_user, req)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.get_subscription(db, current_user, subscription_id)


@router.patch("/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: uuid.UUID,
    req: SubscriptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.update_subscription(db, current_user, subscription_id, req)


@router.post("/{subscription_id}/price-change", response_model=SubscriptionResponse)
def record_subscription_price_change(
    subscription_id: uuid.UUID,
    req: SubscriptionPriceChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.record_price_change(db, current_user, subscription_id, req)


@router.post("/{subscription_id}/pause", response_model=SubscriptionResponse)
def pause_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.pause_subscription(db, current_user, subscription_id)


@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
def resume_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.resume_subscription(db, current_user, subscription_id)


@router.post("/{subscription_id}/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    subscription_id: uuid.UUID,
    req: SubscriptionCancelRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.cancel_subscription(db, current_user, subscription_id, req)


@router.post("/{subscription_id}/archive", response_model=SubscriptionResponse)
def archive_subscription(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.archive_subscription(db, current_user, subscription_id)


@router.post("/{subscription_id}/advance-renewal", response_model=SubscriptionResponse)
def advance_subscription_renewal(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.advance_renewal(db, current_user, subscription_id)


@router.put("/{subscription_id}/reminders", response_model=SubscriptionResponse)
def update_subscription_reminders(
    subscription_id: uuid.UUID,
    req: SubscriptionReminderUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.update_reminders(db, current_user, subscription_id, req)


@router.post("/{subscription_id}/payments", response_model=SubscriptionResponse)
def record_subscription_payment(
    subscription_id: uuid.UUID,
    req: SubscriptionPaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.record_payment(db, current_user, subscription_id, req)


@router.post("/{subscription_id}/payments/link-transaction", response_model=SubscriptionResponse)
def link_subscription_transaction(
    subscription_id: uuid.UUID,
    req: SubscriptionPaymentLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.link_existing_transaction(db, current_user, subscription_id, req)


@router.post(
    "/{subscription_id}/payments/{payment_id}/reverse", response_model=SubscriptionResponse
)
def reverse_subscription_payment(
    subscription_id: uuid.UUID,
    payment_id: uuid.UUID,
    req: SubscriptionPaymentReverseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return sub_service.reverse_payment(db, current_user, subscription_id, payment_id, req)


@router.get("/{subscription_id}/payments", response_model=SubscriptionPaymentListResponse)
def list_subscription_payments(
    subscription_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return sub_service.list_payments(db, current_user, subscription_id=subscription_id)
