import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.models.assistant import AiConversation, AiMessage
from app.models.user import User
from app.repositories.assistant.assistant_repository import AssistantRepository
from app.schemas.assistant import (
    AiConversationCreateRequest,
    AiConversationDetailResponse,
    AiConversationSummaryResponse,
    AiConversationUpdateRequest,
    AiMessageCreateRequest,
    AiMessageResponse,
    ConfirmDraftActionRequest,
    RagReindexResponse,
    UserAiPreferenceResponse,
    UserAiPreferenceUpdateRequest,
    VoiceExpenseDraftResponse,
    WebProviderStatus,
)
from app.services.assistant.assistant_orchestrator import run_assistant_turn
from app.services.assistant.rag_service import reindex_user_documents
from app.services.assistant.voice_service import (
    execute_chat_action_draft,
    parse_voice_expense_transcript,
)
from app.services.web_research.registry import ALLOWED_PROVIDERS, list_provider_statuses


class AssistantService:
    """Service layer managing Phase 10 conversations, messages, RAG lifecycle, preferences & voice drafts."""

    def __init__(self):
        self.repo = AssistantRepository()

    def list_providers(self) -> list[WebProviderStatus]:
        return list_provider_statuses()

    def get_preferences(self, db: Session, user: User) -> UserAiPreferenceResponse:
        pref = self.repo.get_or_create_preference(
            db, user.id, default_provider=settings.DEFAULT_WEB_RESEARCH_PROVIDER
        )
        return UserAiPreferenceResponse.model_validate(pref)

    def update_preferences(
        self, db: Session, user: User, req: UserAiPreferenceUpdateRequest
    ) -> UserAiPreferenceResponse:
        pref = self.repo.get_or_create_preference(
            db, user.id, default_provider=settings.DEFAULT_WEB_RESEARCH_PROVIDER
        )
        if req.default_web_provider is not None:
            pref.default_web_provider = req.default_web_provider
        if req.web_search_enabled is not None:
            pref.web_search_enabled = req.web_search_enabled
        if req.voice_read_aloud_enabled is not None:
            pref.voice_read_aloud_enabled = req.voice_read_aloud_enabled
        if req.auto_execute_actions is not None:
            pref.auto_execute_actions = req.auto_execute_actions
        db.add(pref)
        db.commit()
        db.refresh(pref)
        return UserAiPreferenceResponse.model_validate(pref)

    def list_conversations(
        self, db: Session, user: User
    ) -> list[AiConversationSummaryResponse]:
        rows = self.repo.list_conversations(db, user.id)
        return [AiConversationSummaryResponse.model_validate(r) for r in rows]

    def create_conversation(
        self, db: Session, user: User, req: AiConversationCreateRequest
    ) -> AiConversationDetailResponse:
        pref = self.repo.get_or_create_preference(
            db, user.id, default_provider=settings.DEFAULT_WEB_RESEARCH_PROVIDER
        )
        conv = AiConversation(
            user_id=user.id,
            title=(req.title or "New Financial Chat").strip()[:180],
            preferred_provider=req.preferred_provider or pref.default_web_provider,
            web_search_enabled=req.web_search_enabled,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return AiConversationDetailResponse.model_validate(conv)

    def get_conversation(
        self, db: Session, user: User, conversation_id: uuid.UUID
    ) -> AiConversationDetailResponse:
        conv = self.repo.get_conversation_by_id(
            db, user.id, conversation_id, with_messages=True
        )
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return AiConversationDetailResponse.model_validate(conv)

    def update_conversation(
        self,
        db: Session,
        user: User,
        conversation_id: uuid.UUID,
        req: AiConversationUpdateRequest,
    ) -> AiConversationSummaryResponse:
        conv = self.repo.get_conversation_by_id(db, user.id, conversation_id)
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        if req.title is not None:
            conv.title = req.title.strip()[:180]
        if req.preferred_provider is not None:
            conv.preferred_provider = req.preferred_provider
        if req.web_search_enabled is not None:
            conv.web_search_enabled = req.web_search_enabled
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return AiConversationSummaryResponse.model_validate(conv)

    def delete_conversation(
        self, db: Session, user: User, conversation_id: uuid.UUID
    ) -> None:
        conv = self.repo.get_conversation_by_id(db, user.id, conversation_id)
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        db.delete(conv)
        db.commit()

    def list_messages(
        self, db: Session, user: User, conversation_id: uuid.UUID
    ) -> list[AiMessageResponse]:
        conv = self.repo.get_conversation_by_id(
            db, user.id, conversation_id, with_messages=True
        )
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        return [AiMessageResponse.model_validate(m) for m in conv.messages]

    def send_message(
        self,
        db: Session,
        user: User,
        conversation_id: uuid.UUID,
        req: AiMessageCreateRequest,
    ) -> AiMessageResponse:
        conv = self.repo.get_conversation_by_id(db, user.id, conversation_id)
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        pref = self.repo.get_or_create_preference(
            db, user.id, default_provider=settings.DEFAULT_WEB_RESEARCH_PROVIDER
        )
        selected_provider = (
            req.web_provider or conv.preferred_provider or pref.default_web_provider or "tavily"
        )
        if selected_provider not in ALLOWED_PROVIDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider '{selected_provider}'.",
            )

        web_enabled = (
            req.web_search_enabled if req.web_search_enabled is not None else conv.web_search_enabled
        )

        # Persist user message first
        user_msg = AiMessage(
            conversation_id=conv.id,
            user_id=user.id,
            role="user",
            content=req.content.strip(),
            status="completed",
        )
        db.add(user_msg)
        if conv.title == "New Financial Chat":
            conv.title = req.content.strip()[:60]
        self.repo.touch_conversation(db, conv)
        db.commit()

        history = self.repo.list_recent_messages(
            db, user.id, conv.id, limit=settings.ASSISTANT_MAX_CONTEXT_MESSAGES
        )

        # Exclude the just-saved user message from prior history list so orchestrator appends context cleanly
        prior_history = [m for m in history if m.id != user_msg.id]

        auto_execute = (
            req.auto_execute if req.auto_execute is not None else pref.auto_execute_actions
        )

        result = run_assistant_turn(
            db,
            user,
            query=req.content.strip(),
            history=prior_history,
            web_search_enabled=web_enabled,
            web_provider=selected_provider,
            include_personal_context=req.include_personal_context,
            auto_execute=auto_execute,
        )

        assistant_msg = AiMessage(
            conversation_id=conv.id,
            user_id=user.id,
            role="assistant",
            content=result["content"],
            provider_used=result["provider_used"],
            llm_model=result["llm_model"],
            web_search_used=result["web_search_used"],
            tools_invoked=result["tools_invoked"],
            citations=result["citations"],
            evidence_items=result["evidence_items"],
            draft_action=result.get("draft_action"),
            status="completed",
            error_message=result["error_message"],
        )
        db.add(assistant_msg)
        self.repo.touch_conversation(db, conv)
        db.commit()
        db.refresh(assistant_msg)
        return AiMessageResponse.model_validate(assistant_msg)

    def reindex_documents(self, db: Session, user: User) -> RagReindexResponse:
        scanned, indexed, removed = reindex_user_documents(db, user.id)
        return RagReindexResponse(
            documents_scanned=scanned,
            chunks_indexed=indexed,
            chunks_removed=removed,
        )

    def parse_voice_expense(
        self, db: Session, user: User, transcript: str
    ) -> VoiceExpenseDraftResponse:
        return parse_voice_expense_transcript(db, user, transcript)

    def confirm_message_action(
        self,
        db: Session,
        user: User,
        message_id: uuid.UUID,
        req: ConfirmDraftActionRequest,
    ) -> AiMessageResponse:
        msg = self.repo.get_message_by_id(db, user.id, message_id)
        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Assistant message not found."
            )
        if not msg.draft_action or not isinstance(msg.draft_action, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This message has no confirmable action draft.",
            )

        updated_draft, executed = execute_chat_action_draft(
            db,
            user,
            msg.draft_action,
            overrides=req.model_dump(exclude_none=True),
            execution_mode="confirmed",
            raise_on_incomplete=True,
        )
        if executed:
            msg.draft_action = updated_draft
            flag_modified(msg, "draft_action")
            db.add(msg)
            db.commit()
            db.refresh(msg)
        return AiMessageResponse.model_validate(msg)
