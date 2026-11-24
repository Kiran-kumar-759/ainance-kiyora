import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import UserPreference


class PreferenceRepository:
    """Repository handling database operations for User regional preferences."""

    def get_by_user_id(self, db: Session, user_id: uuid.UUID) -> UserPreference | None:
        query = select(UserPreference).where(UserPreference.user_id == user_id)
        return db.scalars(query).first()

    def create_defaults(
        self,
        db: Session,
        user_id: uuid.UUID,
        preferred_currency: str = "INR",
        locale: str = "en-IN",
        timezone_str: str = "Asia/Kolkata",
        date_format: str = "DD/MM/YYYY",
    ) -> UserPreference:
        now = datetime.now(UTC)
        pref = UserPreference(
            user_id=user_id,
            preferred_currency=preferred_currency,
            locale=locale,
            timezone=timezone_str,
            date_format=date_format,
            notification_preferences={
                "email_alerts": True,
                "bill_reminders": True,
                "monthly_summary": True,
            },
            created_at=now,
            updated_at=now,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
        return pref

    def update(
        self,
        db: Session,
        pref: UserPreference,
        **kwargs,
    ) -> UserPreference:
        for key, value in kwargs.items():
            if value is not None and hasattr(pref, key):
                setattr(pref, key, value)
        pref.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(pref)
        return pref
