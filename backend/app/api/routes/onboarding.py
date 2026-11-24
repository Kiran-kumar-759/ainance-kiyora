from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.models.user import User
from app.schemas.onboarding import OnboardingStatusResponse, OnboardingUpdateRequest
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
