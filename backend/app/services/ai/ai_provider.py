from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.intelligence import GroqCategorizationSchema, GroqInsightNarrativeSchema


@dataclass(frozen=True)
class CategorizationAiInput:
    transaction_type: str
    sanitized_description: str
    sanitized_merchant: str
    amount_band: str
    allowed_categories: tuple[str, ...]


@dataclass(frozen=True)
class InsightNarrativeAiInput:
    insight_type: str
    base_title: str
    base_description: str
    base_action: str | None
    supporting_metrics: dict[str, Any]


class AiProvider(Protocol):
    """Provider-independent interface so Groq can be swapped, mocked, or disabled safely."""

    provider_name: str
    model_name: str

    def is_available(self) -> bool: ...

    def categorize_transaction(
        self, payload: CategorizationAiInput
    ) -> GroqCategorizationSchema | None: ...

    def enrich_insight_narrative(
        self, payload: InsightNarrativeAiInput
    ) -> GroqInsightNarrativeSchema | None: ...


class NullAiProvider:
    """No-op provider used when external AI is disabled or unconfigured."""

    provider_name = "none"
    model_name = "deterministic"

    def is_available(self) -> bool:
        return False

    def categorize_transaction(
        self, payload: CategorizationAiInput
    ) -> GroqCategorizationSchema | None:
        return None

    def enrich_insight_narrative(
        self, payload: InsightNarrativeAiInput
    ) -> GroqInsightNarrativeSchema | None:
        return None
