import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INDIAN_PHONE_RE = re.compile(r"^(?:\+91|91)?([6-9]\d{9})$")


def normalize_indian_phone(phone: str | None) -> str | None:
    """Validates and normalizes an Indian mobile number to +91XXXXXXXXXX format."""
    if not phone:
        return None
    cleaned = re.sub(r"[\s\-()]+", "", phone.strip())
    m = INDIAN_PHONE_RE.match(cleaned)
    if not m:
        return None
    return f"+91{m.group(1)}"


@dataclass
class SmsDeliveryResult:
    delivered: bool
    status: str  # delivered, unavailable, failed
    detail: str
    provider: str = "none"


class SmsProviderAdapter(ABC):
    """Provider-independent SMS adapter interface."""

    @abstractmethod
    def send_sms(self, phone_e164: str, message: str) -> SmsDeliveryResult:
        """Dispatches an SMS reminder and returns honest delivery confirmation."""


class UnconfiguredSmsAdapter(SmsProviderAdapter):
    """Honest fallback when SMS provider credentials are not configured."""

    def send_sms(self, phone_e164: str, message: str) -> SmsDeliveryResult:
        return SmsDeliveryResult(
            delivered=False,
            status="unavailable",
            detail="SMS provider credentials are not configured (SMS_ENABLED=false).",
            provider=settings.SMS_PROVIDER or "none",
        )


class WebhookSmsAdapter(SmsProviderAdapter):
    """Configurable HTTP webhook SMS adapter activated only when credentials exist."""

    def send_sms(self, phone_e164: str, message: str) -> SmsDeliveryResult:
        if not settings.SMS_WEBHOOK_URL or not settings.SMS_API_KEY:
            return SmsDeliveryResult(
                delivered=False,
                status="unavailable",
                detail="SMS_WEBHOOK_URL or SMS_API_KEY is missing.",
                provider="webhook",
            )
        try:
            resp = httpx.post(
                settings.SMS_WEBHOOK_URL,
                json={
                    "to": phone_e164,
                    "sender_id": settings.SMS_SENDER_ID or "PFMIND",
                    "message": message,
                },
                headers={"Authorization": f"Bearer {settings.SMS_API_KEY}"},
                timeout=8.0,
            )
            if 200 <= resp.status_code < 300:
                return SmsDeliveryResult(
                    delivered=True,
                    status="delivered",
                    detail="SMS accepted by configured provider.",
                    provider="webhook",
                )
            return SmsDeliveryResult(
                delivered=False,
                status="failed",
                detail=f"SMS provider returned HTTP {resp.status_code}.",
                provider="webhook",
            )
        except Exception as exc:
            logger.error("SMS webhook dispatch error: %s", exc)
            return SmsDeliveryResult(
                delivered=False,
                status="failed",
                detail=f"SMS delivery failed: {exc}",
                provider="webhook",
            )


class SmsService:
    """Coordinates opt-in, phone validation, and provider adapter dispatch."""

    def is_configured(self) -> bool:
        return bool(
            settings.SMS_ENABLED
            and settings.SMS_PROVIDER != "none"
            and settings.SMS_API_KEY
            and settings.SMS_WEBHOOK_URL
        )

    def _get_adapter(self) -> SmsProviderAdapter:
        if settings.SMS_ENABLED and settings.SMS_PROVIDER == "webhook":
            return WebhookSmsAdapter()
        return UnconfiguredSmsAdapter()

    def send_reminder_sms(
        self,
        raw_phone: str | None,
        sms_opted_in: bool,
        message: str,
    ) -> SmsDeliveryResult:
        if not sms_opted_in:
            return SmsDeliveryResult(
                delivered=False,
                status="unavailable",
                detail="User has not opted into SMS reminders in notification preferences.",
                provider=settings.SMS_PROVIDER,
            )
        phone_e164 = normalize_indian_phone(raw_phone)
        if not phone_e164:
            return SmsDeliveryResult(
                delivered=False,
                status="unavailable",
                detail="No valid Indian mobile number (+91XXXXXXXXXX) configured for user.",
                provider=settings.SMS_PROVIDER,
            )
        if not settings.SMS_ENABLED:
            return UnconfiguredSmsAdapter().send_sms(phone_e164, message)
        return self._get_adapter().send_sms(phone_e164, message)


sms_service = SmsService()
