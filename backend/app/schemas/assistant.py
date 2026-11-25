import datetime as dt
import uuid
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

WebProviderId = Literal["langsearch", "firecrawl", "tavily"]
EvidenceOrigin = Literal[
    "personal_financial_record",
    "personal_document",
    "deterministic_calculation",
    "forecast_or_scenario",
    "external_web",
    "general_explanation",
]


class WebProviderStatus(BaseModel):
    provider: WebProviderId
    display_name: str
    description: str
    configured: bool
    supports_full_text: bool


class UserAiPreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    default_web_provider: WebProviderId
    web_search_enabled: bool
    voice_read_aloud_enabled: bool
    updated_at: dt.datetime


class UserAiPreferenceUpdateRequest(BaseModel):
    default_web_provider: WebProviderId | None = None
    web_search_enabled: bool | None = None
    voice_read_aloud_enabled: bool | None = None


class CitationItem(BaseModel):
    citation_id: int
    evidence_id: str
    origin: EvidenceOrigin
    title: str
    url: str | None = None
    domain: str | None = None
    provider: str | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    origin: EvidenceOrigin
    title: str
    summary: str
    source_reference: str | None = None
    url: str | None = None
    domain: str | None = None
    provider: str | None = None
    published_at: str | None = None
    retrieved_at: str | None = None
    excerpt: str | None = None
    content_available: bool = False
    is_confirmed_source: bool = True
    meta: dict[str, Any] = Field(default_factory=dict)


class VoiceExpenseDraftResponse(BaseModel):
    transcript: str
    transaction_type: Literal["expense", "income"] = "expense"
    amount: Decimal | None = None
    currency: str = "INR"
    category_id: uuid.UUID | None = None
    category_name: str | None = None
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    description: str | None = None
    merchant_payee: str | None = None
    transaction_date: dt.date
    missing_fields: list[str] = Field(default_factory=list)
    requires_user_confirmation: bool = True
    notes: str | None = None


class AiMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    provider_used: str | None = None
    llm_model: str | None = None
    web_search_used: bool = False
    tools_invoked: list[str] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    draft_action: dict[str, Any] | None = None
    status: str
    error_message: str | None = None
    created_at: dt.datetime


class AiConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    preferred_provider: WebProviderId | None = None
    web_search_enabled: bool
    is_archived: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class AiConversationDetailResponse(AiConversationSummaryResponse):
    messages: list[AiMessageResponse] = Field(default_factory=list)


class AiConversationCreateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=180)
    preferred_provider: WebProviderId | None = None
    web_search_enabled: bool = True


class AiConversationUpdateRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=180)
    preferred_provider: WebProviderId | None = None
    web_search_enabled: bool | None = None


class AiMessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2500)
    web_search_enabled: bool | None = None
    web_provider: WebProviderId | None = None
    include_personal_context: bool = True


class VoiceExpenseParseRequest(BaseModel):
    transcript: str = Field(..., min_length=2, max_length=800)


class RagReindexResponse(BaseModel):
    documents_scanned: int
    chunks_indexed: int
    chunks_removed: int


class VoiceTranscribeResponse(BaseModel):
    transcript: str
    provider: str


class VoiceSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
