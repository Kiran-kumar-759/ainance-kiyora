from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.config import settings
from app.core.security import generate_csrf_token, verify_csrf_token_signature
from app.models.user import User
from app.schemas.user import (
    PrivacyDataSummaryResponse,
    UserPreferenceResponse,
    UserPreferenceUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["User Profiles & Preferences"])
user_service = UserService()


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
def get_user_profile(
    response: Response,
    current_user: User = Depends(get_current_user),
    csrf_cookie: str | None = Cookie(None, alias=settings.CSRF_COOKIE_NAME),
):
    """Returns profile information for the authenticated user and heals CSRF cookie if needed."""
    if not csrf_cookie or not verify_csrf_token_signature(csrf_cookie):
        token = generate_csrf_token()
        response.set_cookie(
            key=settings.CSRF_COOKIE_NAME,
            value=token,
            httponly=False,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.SESSION_EXPIRY_SECONDS,
            path="/",
            domain=settings.COOKIE_DOMAIN,
        )
    return user_service.get_profile(current_user)


@router.patch("/me", response_model=UserResponse, summary="Update user profile")
def update_user_profile(
    req: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates permitted profile fields (e.g. full name) for the authenticated user."""
    return user_service.update_profile(db, current_user, req)


@router.get(
    "/me/preferences",
    response_model=UserPreferenceResponse,
    summary="Get user regional preferences",
)
def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves regional preferences (currency, timezone, locale) for current user."""
    return user_service.get_preferences(db, current_user.id)


@router.patch(
    "/me/preferences",
    response_model=UserPreferenceResponse,
    summary="Update user regional preferences",
)
def update_user_preferences(
    req: UserPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    """Updates regional and notification preferences for current user."""
    return user_service.update_preferences(db, current_user.id, req)


@router.get(
    "/me/privacy-summary",
    response_model=PrivacyDataSummaryResponse,
    summary="Get user-owned data inventory & privacy disclosures",
)
def get_privacy_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns tenant-scoped record counts, data handling disclosures, and export links."""
    return user_service.get_privacy_summary(db, current_user)
