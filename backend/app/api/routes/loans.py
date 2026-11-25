import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.loans import (
    EmiCalculatorRequest,
    EmiCalculatorResponse,
    LoanAnalyticsResponse,
    LoanCreateRequest,
    LoanInterestRateRevisionRequest,
    LoanListResponse,
    LoanOverviewResponse,
    LoanPaymentCreateRequest,
    LoanPaymentLinkRequest,
    LoanPaymentListResponse,
    LoanPaymentReverseRequest,
    LoanPrepaymentScenarioRequest,
    LoanPrepaymentScenarioResponse,
    LoanResponse,
    LoanUpdateRequest,
)
from app.services.loans.loan_service import LoanService

router = APIRouter(prefix="/loans", tags=["Loans & EMIs"])
loan_service = LoanService()


@router.post("/calculator", response_model=EmiCalculatorResponse, summary="Deterministic EMI calculator")
def calculate_emi(
    req: EmiCalculatorRequest,
    _: User = Depends(get_current_user),
):
    return loan_service.calculate_emi_preview(req)


@router.post(
    "",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new or existing loan with amortization schedule",
)
def create_loan(
    req: LoanCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.create_loan(db, current_user, req)


@router.get("", response_model=LoanListResponse, summary="List user loans with filters")
def list_loans(
    status_filter: str | None = Query(None),
    loan_type: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("next_due_asc"),
    include_archived: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.list_loans(
        db,
        current_user,
        status_filter=status_filter,
        loan_type=loan_type,
        search=search,
        sort_by=sort_by,
        include_archived=include_archived,
        page=page,
        page_size=page_size,
    )


@router.get("/overview", response_model=LoanOverviewResponse)
def get_loan_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.get_overview(db, current_user)


@router.get("/analytics", response_model=LoanAnalyticsResponse)
def get_loan_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.get_analytics(db, current_user)


@router.get("/payments", response_model=LoanPaymentListResponse)
def list_all_loan_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.list_payments(db, current_user)


@router.get("/{loan_id}", response_model=LoanResponse)
def get_loan(
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.get_loan(db, current_user, loan_id)


@router.patch("/{loan_id}", response_model=LoanResponse)
def update_loan(
    loan_id: uuid.UUID,
    req: LoanUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.update_loan(db, current_user, loan_id, req)


@router.post("/{loan_id}/archive", response_model=LoanResponse)
def archive_loan(
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.archive_loan(db, current_user, loan_id)


@router.post("/{loan_id}/rate-revision", response_model=LoanResponse)
def revise_loan_interest_rate(
    loan_id: uuid.UUID,
    req: LoanInterestRateRevisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.revise_interest_rate(db, current_user, loan_id, req)


@router.post("/{loan_id}/prepayment-scenario", response_model=LoanPrepaymentScenarioResponse)
def simulate_loan_prepayment(
    loan_id: uuid.UUID,
    req: LoanPrepaymentScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.simulate_prepayment(db, current_user, loan_id, req)


@router.post("/{loan_id}/payments", response_model=LoanResponse)
def record_loan_payment(
    loan_id: uuid.UUID,
    req: LoanPaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.record_payment(db, current_user, loan_id, req)


@router.post("/{loan_id}/payments/link-transaction", response_model=LoanResponse)
def link_loan_transaction(
    loan_id: uuid.UUID,
    req: LoanPaymentLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.link_existing_transaction(db, current_user, loan_id, req)


@router.post("/{loan_id}/payments/{payment_id}/reverse", response_model=LoanResponse)
def reverse_loan_payment(
    loan_id: uuid.UUID,
    payment_id: uuid.UUID,
    req: LoanPaymentReverseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return loan_service.reverse_payment(db, current_user, loan_id, payment_id, req)


@router.get("/{loan_id}/payments", response_model=LoanPaymentListResponse)
def list_loan_payments(
    loan_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return loan_service.list_payments(db, current_user, loan_id=loan_id)
