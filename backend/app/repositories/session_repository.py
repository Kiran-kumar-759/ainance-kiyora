import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth import UserSession


class SessionRepository:
    """Repository handling database operations for server-managed sessions."""

    def create(
        self,
        db: Session,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        now = datetime.now(UTC)
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            expires_at=expires_at,
            last_used_at=now,
            revoked_at=None,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_by_token_hash(self, db: Session, token_hash: str) -> UserSession | None:
        query = select(UserSession).where(UserSession.token_hash == token_hash)
        return db.scalars(query).first()

    def list_active_by_user(self, db: Session, user_id: uuid.UUID) -> list[UserSession]:
        now = datetime.now(UTC)
        query = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .order_by(UserSession.last_used_at.desc())
        )
        return list(db.scalars(query).all())

    def revoke(self, db: Session, session_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Revokes a specific session, enforcing strict user ownership."""
        now = datetime.now(UTC)
        stmt = (
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    def revoke_all_for_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        except_session_id: uuid.UUID | None = None,
    ) -> int:
        """Revokes all active sessions for a user, with optional current session exemption."""
        now = datetime.now(UTC)
        stmt = update(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
        if except_session_id:
            stmt = stmt.where(UserSession.id != except_session_id)

        stmt = stmt.values(revoked_at=now)
        result = db.execute(stmt)
        db.commit()
        return result.rowcount

    def update_last_used(self, db: Session, session: UserSession) -> None:
        session.last_used_at = datetime.now(UTC)
        db.commit()
