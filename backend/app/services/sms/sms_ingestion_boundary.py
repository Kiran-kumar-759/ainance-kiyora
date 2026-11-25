from abc import ABC, abstractmethod

from app.core.config import settings
from app.schemas.email_ingestion import SmsIngestionStatusResponse


class SmsIngestionProvider(ABC):
    @abstractmethod
    def get_status(self) -> SmsIngestionStatusResponse: ...


class UnavailableSmsIngestionProvider(SmsIngestionProvider):
    """
    Compliant boundary for incoming SMS extraction.
    A pure browser SaaS application cannot read device SMS inboxes directly,
    and no native Android companion app or telecom SMS webhook is configured here.
    Phase 5 outgoing SMS bill reminders remain unaffected.
    """

    def get_status(self) -> SmsIngestionStatusResponse:
        return SmsIngestionStatusResponse(
            enabled=settings.SMS_INGESTION_ENABLED,
            provider=settings.SMS_INGESTION_PROVIDER,
            available=False,
            outgoing_reminders_active=True,
            limitation_reason=(
                "Incoming SMS transaction ingestion is currently unavailable: this web SaaS "
                "environment cannot access Android SMS inboxes directly, and no external "
                "Android companion or consent-based SMS bridge is configured."
            ),
            supported_platforms_note=(
                "To prevent unsafe permission bypasses or inbox scraping, SMS ingestion requires "
                "a future explicit-consent Android companion integration. Outgoing SMS reminders "
                "from Phase 5 continue functioning independently."
            ),
        )


def get_sms_ingestion_provider() -> SmsIngestionProvider:
    return UnavailableSmsIngestionProvider()
