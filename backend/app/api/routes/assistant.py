import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, verify_csrf
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.assistant import (
    AiConversationCreateRequest,
    AiConversationDetailResponse,
    AiConversationSummaryResponse,
    AiConversationUpdateRequest,
    AiMessageCreateRequest,
    AiMessageResponse,
    RagReindexResponse,
    UserAiPreferenceResponse,
    UserAiPreferenceUpdateRequest,
    VoiceExpenseDraftResponse,
    VoiceExpenseParseRequest,
    WebProviderStatus,
)
from app.services.assistant.assistant_service import AssistantService

router = APIRouter(prefix="/assistant", tags=["AI Personal Finance Assistant"])
assistant_service = AssistantService()


def _enforce_assistant_rate_limit(user_id: uuid.UUID, op: str, max_requests: int = 25) -> None:
    allowed = rate_limiter.is_allowed(
        f"assistant:{op}:{user_id}",
        max_requests=max_requests,
        window_seconds=60,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI Assistant rate limit exceeded. Please wait a minute and retry.",
        )


@router.get("/providers", response_model=list[WebProviderStatus])
def list_web_providers(current_user: User = Depends(get_current_user)):
    return assistant_service.list_providers()


@router.get("/preferences", response_model=UserAiPreferenceResponse)
def get_ai_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return assistant_service.get_preferences(db, current_user)


@router.patch("/preferences", response_model=UserAiPreferenceResponse)
def update_ai_preferences(
    payload: UserAiPreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return assistant_service.update_preferences(db, current_user, payload)


@router.get("/conversations", response_model=list[AiConversationSummaryResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return assistant_service.list_conversations(db, current_user)


@router.post(
    "/conversations",
    response_model=AiConversationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: AiConversationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return assistant_service.create_conversation(db, current_user, payload)


@router.get("/conversations/{conversation_id}", response_model=AiConversationDetailResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return assistant_service.get_conversation(db, current_user, conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=AiConversationSummaryResponse)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: AiConversationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    return assistant_service.update_conversation(db, current_user, conversation_id, payload)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    assistant_service.delete_conversation(db, current_user, conversation_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[AiMessageResponse])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return assistant_service.list_messages(db, current_user, conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=AiMessageResponse)
def send_message(
    conversation_id: uuid.UUID,
    payload: AiMessageCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_assistant_rate_limit(current_user.id, "chat", max_requests=20)
    return assistant_service.send_message(db, current_user, conversation_id, payload)


@router.post("/rag/reindex", response_model=RagReindexResponse)
def reindex_rag_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_assistant_rate_limit(current_user.id, "rag", max_requests=10)
    return assistant_service.reindex_documents(db, current_user)


@router.post("/voice/parse-expense", response_model=VoiceExpenseDraftResponse)
def parse_voice_expense(
    payload: VoiceExpenseParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(verify_csrf),
):
    _enforce_assistant_rate_limit(current_user.id, "voice", max_requests=30)
    return assistant_service.parse_voice_expense(db, current_user, payload.transcript)
