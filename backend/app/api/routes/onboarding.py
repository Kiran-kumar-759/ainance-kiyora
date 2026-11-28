from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.onboarding import (
    DashboardAccessResponse,
    InitializationStatusResponse,
    OnboardingComprehensiveStatusResponse,
    OnboardingFinancialSetupSelectRequest,
    OnboardingInitializeRequest,
    OnboardingProfileRequest,
    OnboardingSkipFinancialSetupRequest,
    OnboardingStatusResponse,
    OnboardingUpdateRequest,
)
from app.services.onboarding_service import OnboardingService

router = APIRouter(prefix="/onboarding", tags=["User Onboarding"])
onboarding_service = OnboardingService()


@router.get("", response_model=OnboardingStatusResponse, summary="Get onboarding status")
def get_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves current onboarding completion status and initial preferences."""
    return onboarding_service.get_status(db, current_user)


@router.get(
    "/status",
    response_model=OnboardingComprehensiveStatusResponse,
    summary="Get consolidated onboarding, setup, and readiness status",
)
def get_consolidated_onboarding_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns unified first-time onboarding progress, selected setup method, real banking/account/
    import/document readiness counts, initialization steps, and next recommended action.
    """
    return onboarding_service.get_comprehensive_status(db, current_user)


@router.patch("", response_model=OnboardingStatusResponse, summary="Update onboarding preferences")
def update_onboarding_step(
    req: OnboardingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates optional profile and regional preferences during the onboarding wizard."""
    return onboarding_service.update_step(db, current_user, req)


@router.post(
    "/profile",
    response_model=OnboardingComprehensiveStatusResponse,
    summary="Save onboarding profile and Indian regional preferences",
)
def save_onboarding_profile(
    req: OnboardingProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Persists profile details and Indian preferences and advances to financial setup."""
    return onboarding_service.save_profile_and_preferences(db, current_user, req)


@router.post(
    "/financial-setup/select",
    response_model=OnboardingComprehensiveStatusResponse,
    summary="Select financial data setup method",
)
def select_financial_setup_method(
    req: OnboardingFinancialSetupSelectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Persists the user's chosen onboarding financial-data setup method."""
    return onboarding_service.select_financial_setup_method(db, current_user, req)


@router.post(
    "/financial-setup/skip",
    response_model=OnboardingComprehensiveStatusResponse,
    summary="Skip financial data setup safely",
)
def skip_financial_setup(
    req: OnboardingSkipFinancialSetupRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Skips bank connection and manual financial setup without fabricating data."""
    return onboarding_service.skip_financial_setup(
        db, current_user, req or OnboardingSkipFinancialSetupRequest()
    )


@router.post(
    "/initialize",
    response_model=InitializationStatusResponse,
    summary="Initialize user financial workspace from real PostgreSQL records",
)
def initialize_workspace(
    req: OnboardingInitializeRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Runs idempotent workspace initialization across user-owned accounts, transactions, and documents."""
    return onboarding_service.initialize_workspace(
        db, current_user, force=(req.force if req else False)
    )


@router.post(
    "/initialize/retry",
    response_model=InitializationStatusResponse,
    summary="Retry failed workspace initialization",
)
def retry_workspace_initialization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Retries workspace initialization cleanly following a prior step failure."""
    return onboarding_service.initialize_workspace(db, current_user, force=True)


@router.get(
    "/initialization-status",
    response_model=InitializationStatusResponse,
    summary="Get workspace initialization progress",
)
def get_initialization_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns persisted step-by-step workspace initialization progress."""
    return onboarding_service.get_initialization_status(db, current_user)


@router.get(
    "/dashboard-access",
    response_model=DashboardAccessResponse,
    summary="Check whether dashboard access is permitted for authenticated user",
)
def check_dashboard_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns 200 when onboarding is completed, or 403 when onboarding is still required."""
    return onboarding_service.check_dashboard_access(db, current_user)


@router.post(
    "/complete",
    response_model=OnboardingStatusResponse,
    summary="Complete onboarding workflow",
)
def complete_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Marks onboarding completed in PostgreSQL."""
    return onboarding_service.complete_onboarding(db, current_user)


@router.post(
    "/skip",
    response_model=OnboardingStatusResponse,
    summary="Skip optional onboarding workflow",
)
def skip_onboarding(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Skips all optional onboarding steps and marks onboarding completed."""
    return onboarding_service.skip_onboarding(db, current_user)
