import json
import re
from collections.abc import Iterable

from pydantic import ValidationError

from app.schemas.intelligence import GroqCategorizationSchema, GroqInsightNarrativeSchema

# Redact account numbers, card numbers, phone numbers, email addresses, and PAN-like IDs before LLM calls
_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{9,18}\b"), "[ACCOUNT_NUM]"),
    (re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"), "[CARD_NUM]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I), "[TAX_ID]"),
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.I), "[IFSC]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b[A-Za-z0-9._-]+@[A-Za-z]{2,}\b"), "[UPI_VPA]"),
    (re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"), "[PHONE]"),
)


def sanitize_text_for_ai(text: str | None) -> str:
    """Strip sensitive PII / banking identifiers before sending text to any external AI provider."""
    if not text:
        return ""
    cleaned = text.strip()
    for pat, replacement in _REDACTION_PATTERNS:
        cleaned = pat.sub(replacement, cleaned)
    return cleaned[:220]


def validate_groq_categorization(
    raw_content: str,
    allowed_categories: Iterable[str],
) -> GroqCategorizationSchema | None:
    """Parse JSON from LLM and verify schema + allowed category strictly."""
    try:
        payload = json.loads(raw_content)
        parsed = GroqCategorizationSchema.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None

    allowed_map = {c.lower(): c for c in allowed_categories}
    matched = allowed_map.get(parsed.suggested_category.strip().lower())
    if not matched:
        return None
    parsed.suggested_category = matched
    return parsed


def validate_groq_insight_narrative(raw_content: str) -> GroqInsightNarrativeSchema | None:
    """Parse JSON from LLM for insight summary enrichment strictly."""
    try:
        payload = json.loads(raw_content)
        return GroqInsightNarrativeSchema.model_validate(payload)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None
