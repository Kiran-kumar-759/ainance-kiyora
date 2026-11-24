import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.models.user import User


class UserRepository:
    """Repository handling database operations for User accounts."""

    def get_by_id(self, db: Session, user_id: uuid.UUID) -> User | None:
        query = select(User).where(User.id == user_id)
        return db.scalars(query).first()

    def get_by_email(self, db: Session, email: str) -> User | None:
        clean_email = normalize_email(email)
        query = select(User).where(User.email == clean_email)
        return db.scalars(query).first()

    def create(
        self,
        db: Session,
        email: str,
        password_hash: str,
        full_name: str,
        is_email_verified: bool = False,
    ) -> User:
        clean_email = normalize_email(email)
        user = User(
            email=clean_email,
            password_hash=password_hash,
            full_name=full_name.strip(),
            is_active=True,
            is_email_verified=is_email_verified,
            onboarding_completed=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def update_last_login(self, db: Session, user: User) -> None:
        user.last_login_at = datetime.now(UTC)
        db.commit()

    def update(self, db: Session, user: User, **kwargs) -> User:
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(user)
        return user
