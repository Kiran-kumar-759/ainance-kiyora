import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth import EmailVerificationToken, PasswordResetToken


class TokenRepository:
    """Repository handling one-time hashed tokens for email verification and password resets."""

    # --- Email Verification Tokens ---
    def create_verification_token(
        self,
        db: Session,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> EmailVerificationToken:
        token = EmailVerificationToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
            used_at=None,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token

    def get_verification_token(
        self,
        db: Session,
        token_hash: str,
    ) -> EmailVerificationToken | None:
        query = select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash
        )
        return db.scalars(query).first()

    def mark_verification_used(
        self,
        db: Session,
        token_hash: str,
    ) -> bool:
        """
        Atomically marks a verification token as used IF AND ONLY IF used_at IS NULL.
        Returns True if this operation successfully claimed the token, False if already consumed or expired.
        """
        now = datetime.now(UTC)
        stmt = (
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.token_hash == token_hash,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.expires_at > now,
            )
            .values(used_at=now)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def invalidate_pending_verification_tokens(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        db.execute(stmt)
        db.commit()

    # --- Password Reset Tokens ---
    def create_reset_token(
        self,
        db: Session,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
            used_at=None,
        )
        db.add(token)
        db.commit()
        db.refresh(token)
        return token

    def get_reset_token(
        self,
        db: Session,
        token_hash: str,
    ) -> PasswordResetToken | None:
        query = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        return db.scalars(query).first()

    def mark_reset_used(
        self,
        db: Session,
        token_hash: str,
    ) -> bool:
        """
        Atomically marks a password reset token as used IF AND ONLY IF used_at IS NULL.
        Returns True if this operation successfully claimed the token, False if already consumed or expired.
        """
        now = datetime.now(UTC)
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(used_at=now)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def invalidate_pending_reset_tokens(
        self,
        db: Session,
        user_id: uuid.UUID,
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=now)
        )
        db.execute(stmt)
        db.commit()
