import json
import logging

from app.core.config import settings
from app.schemas.intelligence import GroqCategorizationSchema, GroqInsightNarrativeSchema
from app.services.ai.ai_provider import CategorizationAiInput, InsightNarrativeAiInput
from app.services.ai.ai_validation import (
    validate_groq_categorization,
    validate_groq_insight_narrative,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION_CATEGORIZATION = "cat_v1"
PROMPT_VERSION_INSIGHT = "insight_v1"


class GroqAiProvider:
    """
    Optional Groq SDK adapter with strict timeout, retry, JSON mode, Pydantic validation,
    and automatic deterministic fallback on any error or missing configuration.
    Never logs API keys or raw sensitive banking fields.
    """

    provider_name = "groq"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ):
        self._api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model_name = model_name or settings.GROQ_MODEL
        self._enabled = settings.GROQ_ENABLED if enabled is None else enabled
        self._timeout = timeout_seconds or settings.GROQ_TIMEOUT_SECONDS
        self._max_retries = settings.GROQ_MAX_RETRIES if max_retries is None else max_retries

    def is_available(self) -> bool:
        return bool(self._enabled and self._api_key and self._api_key.strip())

    def _build_client(self):
        from groq import Groq

        return Groq(
            api_key=self._api_key,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )

    def categorize_transaction(
        self, payload: CategorizationAiInput
    ) -> GroqCategorizationSchema | None:
        if not self.is_available() or not payload.allowed_categories:
            return None

        system_prompt = (
            "You are an Indian personal finance transaction categorization engine. "
            "Respond ONLY with valid JSON containing keys: "
            "suggested_category (exact string from allowed_categories), "
            "normalized_merchant (string or null), "
            "confidence (float 0.0 to 1.0), "
            "explanation (concise 1-sentence reason). "
            "Never invent categories outside allowed_categories."
        )
        user_payload = {
            "transaction_type": payload.transaction_type,
            "description": payload.sanitized_description,
            "merchant_payee": payload.sanitized_merchant,
            "amount_band": payload.amount_band,
            "allowed_categories": list(payload.allowed_categories),
        }

        try:
            client = self._build_client()
            candidate_models = [self.model_name] + [
                m for m in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b") if m != self.model_name
            ]
            for model_id in candidate_models:
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        temperature=0.0,
                        max_tokens=512,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_payload)},
                        ],
                    )
                    content = response.choices[0].message.content or ""
                    parsed = validate_groq_categorization(content, payload.allowed_categories)
                    if parsed is not None:
                        self.model_name = model_id
                        return parsed
                except Exception as inner_exc:
                    if type(inner_exc).__name__ in ("NotFoundError", "BadRequestError"):
                        continue
                    raise
            return None
        except Exception as exc:
            logger.warning("Groq categorization fallback to local mode: %s", type(exc).__name__)
            return None

    def enrich_insight_narrative(
        self, payload: InsightNarrativeAiInput
    ) -> GroqInsightNarrativeSchema | None:
        if not self.is_available():
            return None

        system_prompt = (
            "You are a financial clarity assistant for Indian users. "
            "Rewrite the deterministic spending insight into concise, polite, plain English "
            "using ONLY the provided metrics — never invent numbers or predictions. "
            "Respond ONLY with valid JSON keys: title, description, suggested_action."
        )
        user_payload = {
            "insight_type": payload.insight_type,
            "base_title": payload.base_title,
            "base_description": payload.base_description,
            "base_action": payload.base_action,
            "metrics": payload.supporting_metrics,
        }

        try:
            client = self._build_client()
            candidate_models = [self.model_name] + [
                m for m in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b") if m != self.model_name
            ]
            for model_id in candidate_models:
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        temperature=0.1,
                        max_tokens=512,
                        response_format={"type": "json_object"},
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": json.dumps(user_payload)},
                        ],
                    )
                    content = response.choices[0].message.content or ""
                    parsed = validate_groq_insight_narrative(content)
                    if parsed is not None:
                        self.model_name = model_id
                        return parsed
                except Exception as inner_exc:
                    if type(inner_exc).__name__ in ("NotFoundError", "BadRequestError"):
                        continue
                    raise
            return None
        except Exception as exc:
            logger.warning("Groq insight enrichment fallback to local text: %s", type(exc).__name__)
            return None


def get_ai_provider() -> GroqAiProvider:
    return GroqAiProvider()
