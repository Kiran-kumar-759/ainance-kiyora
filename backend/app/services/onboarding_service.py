from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.user_repository import UserRepository
from app.schemas.onboarding import OnboardingStatusResponse, OnboardingUpdateRequest
from app.schemas.user import UserPreferenceResponse


class OnboardingService:
    """Service orchestrating multi-step user onboarding and state persistence."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        pref_repo: PreferenceRepository | None = None,
    ):
        self.user_repo = user_repo or UserRepository()
        self.pref_repo = pref_repo or PreferenceRepository()

    def get_status(self, db: Session, user: User) -> OnboardingStatusResponse:
        pref = self.pref_repo.get_by_user_id(db, user.id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user.id)

        current_step = 1
        if (
            pref
            and pref.notification_preferences
            and isinstance(pref.notification_preferences, dict)
        ):
            current_step = int(pref.notification_preferences.get("current_step", 1))

        return OnboardingStatusResponse(
            onboarding_completed=user.onboarding_completed,
            is_email_verified=user.is_email_verified,
            full_name=user.full_name,
            current_step=current_step,
            preferences=UserPreferenceResponse.model_validate(pref),
        )

    def update_step(
        self,
        db: Session,
        user: User,
        req: OnboardingUpdateRequest,
    ) -> OnboardingStatusResponse:
        """Updates optional profile and regional preferences during onboarding."""
        if req.full_name is not None and req.full_name.strip():
            self.user_repo.update(db, user, full_name=req.full_name.strip())

        pref = self.pref_repo.get_by_user_id(db, user.id)
        if not pref:
            pref = self.pref_repo.create_defaults(db, user.id)

        pref_updates = {}
        if req.preferred_currency is not None:
            pref_updates["preferred_currency"] = req.preferred_currency
        if req.locale is not None:
            pref_updates["locale"] = req.locale
        if req.timezone is not None:
            pref_updates["timezone"] = req.timezone
        if req.date_format is not None:
            pref_updates["date_format"] = req.date_format

        current_notifs = (
            dict(pref.notification_preferences)
            if isinstance(pref.notification_preferences, dict)
            else {}
        )
        if req.current_step is not None:
            current_notifs["current_step"] = req.current_step
        if req.notification_preferences is not None:
            current_notifs.update(req.notification_preferences)
        pref_updates["notification_preferences"] = current_notifs

        self.pref_repo.update(db, pref, **pref_updates)

        return self.get_status(db, user)

    def complete_onboarding(self, db: Session, user: User) -> OnboardingStatusResponse:
        """Finalizes onboarding and persists completion status in PostgreSQL."""
        self.user_repo.update(db, user, onboarding_completed=True)
        return self.get_status(db, user)

    def skip_onboarding(self, db: Session, user: User) -> OnboardingStatusResponse:
        """Allows user to skip all optional onboarding setup steps."""
        self.user_repo.update(db, user, onboarding_completed=True)
        return self.get_status(db, user)
