import datetime as dt
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.assistant import AiConversation, AiMessage, UserAiPreference


class AssistantRepository:
    """Tenant-scoped repository for Phase 10 AI Assistant conversations, messages & preferences."""

    def get_or_create_preference(
        self, db: Session, user_id: uuid.UUID, *, default_provider: str = "tavily"
    ) -> UserAiPreference:
        pref = db.execute(
            select(UserAiPreference).where(UserAiPreference.user_id == user_id)
        ).scalar_one_or_none()
        if pref is None:
            pref = UserAiPreference(
                user_id=user_id,
                default_web_provider=default_provider,
                web_search_enabled=True,
                voice_read_aloud_enabled=False,
            )
            db.add(pref)
            db.commit()
            db.refresh(pref)
        return pref

    def list_conversations(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 40
    ) -> list[AiConversation]:
        stmt = (
            select(AiConversation)
            .where(AiConversation.user_id == user_id, AiConversation.is_archived.is_(False))
            .order_by(desc(AiConversation.updated_at))
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_conversation_by_id(
        self,
        db: Session,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        with_messages: bool = False,
    ) -> AiConversation | None:
        stmt = select(AiConversation).where(
            AiConversation.id == conversation_id,
            AiConversation.user_id == user_id,
        )
        if with_messages:
            stmt = stmt.options(selectinload(AiConversation.messages))
        return db.execute(stmt).scalar_one_or_none()

    def list_recent_messages(
        self,
        db: Session,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        *,
        limit: int = 12,
    ) -> list[AiMessage]:
        stmt = (
            select(AiMessage)
            .where(
                AiMessage.conversation_id == conversation_id,
                AiMessage.user_id == user_id,
            )
            .order_by(desc(AiMessage.created_at))
            .limit(limit)
        )
        rows = list(db.execute(stmt).scalars().all())
        rows.reverse()
        return rows

    def touch_conversation(self, db: Session, conv: AiConversation) -> None:
        conv.updated_at = dt.datetime.now(dt.UTC)
        db.add(conv)
