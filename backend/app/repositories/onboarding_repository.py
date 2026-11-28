import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.onboarding import UserOnboardingState


class OnboardingRepository:
    """Repository managing persisted per-user onboarding state machine records."""

    def get_by_user_id(self, db: Session, user_id: uuid.UUID) -> UserOnboardingState | None:
        stmt = select(UserOnboardingState).where(UserOnboardingState.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    def get_or_create(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        already_completed: bool = False,
    ) -> UserOnboardingState:
        existing = self.get_by_user_id(db, user_id)
        if existing is not None:
            return existing

        stage = "completed" if already_completed else "registered"
        completed = ["registered", "completed"] if already_completed else ["registered"]
        step = 5 if already_completed else 1
        state = UserOnboardingState(
            user_id=user_id,
            current_stage=stage,
            completed_stages=completed,
            current_step=step,
            profile_completed=already_completed,
            financial_setup_status="completed" if already_completed else "not_started",
            financial_setup_skipped=False,
            financial_profile={"country": "India", "financial_year": "April-March"},
            initialization_status="completed" if already_completed else "not_started",
            initialization_steps=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def save(self, db: Session, state: UserOnboardingState, *, commit: bool = True) -> UserOnboardingState:
        state.updated_at = datetime.now(UTC)
        db.add(state)
        db.flush()
        if commit:
            db.commit()
            db.refresh(state)
        return state
