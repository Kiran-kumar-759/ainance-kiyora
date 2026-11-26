import datetime as dt
import smtplib
import time
import uuid
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assistant import AiMessage, UserAiPreference
from app.models.email_ingestion import EmailConnection
from app.models.intelligence import AiProcessingJob
from app.models.user import User
from app.providers.banking.demo_provider import get_all_demo_providers
from app.schemas.integrations import (
    IntegrationConnectionSummary,
    IntegrationDisconnectResponse,
    IntegrationItemResponse,
    IntegrationsOverviewResponse,
    IntegrationTestResponse,
)
from app.services.ai.groq_provider import GroqAiProvider
from app.services.banking.banking_service import BankingService
from app.services.bills.sms_service import sms_service
from app.services.email.email_ingestion_service import EmailIngestionService
from app.services.email.token_crypto import decrypt_oauth_token
from app.services.sms.sms_ingestion_boundary import get_sms_ingestion_provider
from app.services.web_research.registry import list_provider_statuses
from app.services.web_research.research_service import WebResearchService
from app.services.web_research.source_validation import is_safe_public_url


class IntegrationService:
    """
    Unified read/test/disconnect orchestration for the Integrations Center.
    Reuses existing Phase 2-10 services cleanly without duplicating state or leaking secrets.
    """

    def __init__(
        self,
        *,
        banking_service: BankingService | None = None,
        email_service: EmailIngestionService | None = None,
        web_research_service: WebResearchService | None = None,
    ):
        self.banking_service = banking_service or BankingService()
        self.email_service = email_service or EmailIngestionService()
        self.web_research_service = web_research_service or WebResearchService()

    @staticmethod
    def _safe_host_from_url(raw_url: str | None) -> str | None:
        if not raw_url:
            return None
        try:
            parsed = urlparse(raw_url)
            return parsed.hostname
        except Exception:
            return None

    def _get_or_init_ai_pref(self, db: Session, user_id: uuid.UUID) -> tuple[str, bool]:
        pref = db.execute(
            select(UserAiPreference).where(UserAiPreference.user_id == user_id)
        ).scalar_one_or_none()
        if pref is None:
            return settings.DEFAULT_WEB_RESEARCH_PROVIDER, True
        return pref.default_web_provider, bool(pref.web_search_enabled)

    def _latest_groq_telemetry(
        self, db: Session, user_id: uuid.UUID
    ) -> tuple[dt.datetime | None, str | None]:
        msg_ts = db.execute(
            select(AiMessage.created_at)
            .where(AiMessage.user_id == user_id, AiMessage.llm_model.is_not(None))
            .order_by(desc(AiMessage.created_at))
            .limit(1)
        ).scalar_one_or_none()
        job = db.execute(
            select(AiProcessingJob)
            .where(AiProcessingJob.user_id == user_id, AiProcessingJob.provider_name == "groq")
            .order_by(desc(AiProcessingJob.created_at))
            .limit(1)
        ).scalar_one_or_none()
        job_ts = job.completed_at if job and job.status == "completed" else None
        latest_ts = max((t for t in (msg_ts, job_ts) if t is not None), default=None)
        last_err = job.error_message if job and job.status == "failed" else None
        return latest_ts, last_err

    def _latest_web_telemetry(
        self, db: Session, user_id: uuid.UUID, provider_id: str
    ) -> tuple[dt.datetime | None, str | None]:
        msg = db.execute(
            select(AiMessage)
            .where(
                AiMessage.user_id == user_id,
                AiMessage.provider_used == provider_id,
            )
            .order_by(desc(AiMessage.created_at))
            .limit(1)
        ).scalar_one_or_none()
        if not msg:
            return None, None
        return msg.created_at, msg.error_message

    def _build_items_and_connections(
        self, db: Session, user: User
    ) -> tuple[list[IntegrationItemResponse], list[IntegrationConnectionSummary], str, bool]:
        preferred_web, web_enabled = self._get_or_init_ai_pref(db, user.id)

        # 1. Banking (Demo + Planned Open Banking)
        bank_conns = self.banking_service.list_user_connections(db, user)
        active_bank_conns = [c for c in bank_conns if c.status == "connected"]
        demo_providers = get_all_demo_providers()
        latest_bank_sync = max(
            (c.last_sync_at for c in bank_conns if c.last_sync_at is not None),
            default=None,
        )
        connected_demo_accounts = sum(c.connected_accounts_count for c in active_bank_conns)

        items: list[IntegrationItemResponse] = [
            IntegrationItemResponse(
                provider_id="demo_banking",
                name="Demo Banking Simulator",
                category="banking",
                description="Simulated Indian banks for consent testing, account discovery, and idempotent ledger sync.",
                status="connected" if active_bank_conns else "available",
                configured=True,
                connected=len(active_bank_conns) > 0,
                available=True,
                can_test=True,
                can_connect=True,
                capabilities=[
                    "Explicit Consent Simulation",
                    "Account Discovery & Balance Import",
                    "Idempotent Demo Transaction Sync",
                ],
                last_sync_or_test_at=latest_bank_sync,
                safe_metadata={
                    "simulated": True,
                    "institutions_available": len(demo_providers),
                    "active_connections": len(active_bank_conns),
                    "connected_accounts_count": connected_demo_accounts,
                },
            ),
            IntegrationItemResponse(
                provider_id="account_aggregator",
                name="India Account Aggregator / Live Open Banking",
                category="banking",
                description="Direct RBI-regulated Account Aggregator bank feeds are not configured in this release. Use Bank Statement CSV/XLSX Imports or Demo Banking.",
                status="planned",
                configured=False,
                connected=False,
                available=False,
                is_planned=True,
                can_test=True,
                capabilities=["Not Implemented in Current Release"],
                safe_metadata={
                    "alternatives": ["CSV / XLSX Bank Statement Import", "Demo Banking Simulator"]
                },
            ),
        ]

        connections: list[IntegrationConnectionSummary] = [
            IntegrationConnectionSummary(
                connection_id=c.id,
                connection_type="banking",
                provider_id=c.provider_id,
                display_name=c.institution_name,
                status=c.status,
                linked_accounts_count=c.connected_accounts_count,
                last_sync_at=c.last_sync_at,
                can_disconnect=(c.status == "connected"),
            )
            for c in bank_conns
        ]

        # 2. Email / Gmail OAuth
        email_conns = self.email_service.get_connections(db, user)
        gmail_conn_row = db.execute(
            select(EmailConnection).where(
                EmailConnection.user_id == user.id,
                EmailConnection.provider == "gmail",
            )
        ).scalar_one_or_none()
        gmail_oauth_configured = bool(
            settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
        )
        gmail_connected = bool(gmail_conn_row and gmail_conn_row.status == "connected")
        gmail_status = "unavailable"
        if gmail_connected:
            if gmail_conn_row and gmail_conn_row.last_error:
                gmail_status = "error"
            elif (
                gmail_conn_row
                and gmail_conn_row.token_expires_at
                and gmail_conn_row.token_expires_at < dt.datetime.now(dt.UTC)
                and not gmail_conn_row.encrypted_refresh_token
            ):
                gmail_status = "error"
            else:
                gmail_status = "connected"
        elif gmail_oauth_configured:
            gmail_status = "configured_not_connected"

        items.append(
            IntegrationItemResponse(
                provider_id="gmail",
                name="Gmail OAuth (Read-Only)",
                category="email",
                description="Reads bills, statements, and receipts from your Gmail inbox using read-only OAuth 2.0 and Fernet-encrypted server-side tokens.",
                status=gmail_status,  # type: ignore[arg-type]
                configured=gmail_oauth_configured,
                connected=gmail_connected,
                available=gmail_oauth_configured,
                can_test=True,
                can_connect=gmail_oauth_configured and not gmail_connected,
                can_disconnect=gmail_connected,
                capabilities=[
                    "Read-Only Inbox Scanning (gmail.readonly)",
                    "PDF & Invoice Attachment Ingestion",
                    "Human-Confirmed Candidate Import",
                ],
                required_env_vars=(
                    []
                    if gmail_oauth_configured
                    else [
                        "GOOGLE_OAUTH_CLIENT_ID",
                        "GOOGLE_OAUTH_CLIENT_SECRET",
                        "GOOGLE_OAUTH_REDIRECT_URI",
                    ]
                ),
                last_sync_or_test_at=gmail_conn_row.last_sync_at if gmail_conn_row else None,
                last_error=gmail_conn_row.last_error if gmail_conn_row else None,
                safe_metadata={
                    "authorized_email": gmail_conn_row.email_address if gmail_conn_row else None,
                    "token_expires_at": (
                        gmail_conn_row.token_expires_at.isoformat()
                        if gmail_conn_row and gmail_conn_row.token_expires_at
                        else None
                    ),
                    "scopes": list(gmail_conn_row.scopes or settings.GMAIL_SCOPES)
                    if gmail_conn_row
                    else list(settings.GMAIL_SCOPES),
                    "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                },
            )
        )

        if gmail_conn_row:
            ec = email_conns[0] if email_conns else None
            connections.append(
                IntegrationConnectionSummary(
                    connection_id=gmail_conn_row.id,
                    connection_type="email",
                    provider_id="gmail",
                    display_name="Gmail OAuth (Read-Only)",
                    status=gmail_conn_row.status,
                    account_or_email=gmail_conn_row.email_address,
                    scopes=list(gmail_conn_row.scopes or []),
                    token_expires_at=gmail_conn_row.token_expires_at,
                    last_sync_at=ec.last_sync_at if ec else gmail_conn_row.last_sync_at,
                    last_error=gmail_conn_row.last_error,
                    can_disconnect=(gmail_conn_row.status == "connected"),
                )
            )

        # 3. SMS (Outgoing Webhook vs Incoming Ingestion Boundary)
        sms_out_configured = sms_service.is_configured()
        sms_url_safe, _, sms_domain = is_safe_public_url(settings.SMS_WEBHOOK_URL)
        sms_out_status = "unavailable"
        sms_out_err = None
        if settings.SMS_ENABLED:
            if sms_out_configured and sms_url_safe:
                sms_out_status = "connected"
            else:
                sms_out_status = "error"
                sms_out_err = (
                    "SMS_WEBHOOK_URL failed SSRF policy or SMS credentials are incomplete."
                    if settings.SMS_WEBHOOK_URL and not sms_url_safe
                    else "SMS_ENABLED is true but webhook URL or API key is missing."
                )

        items.append(
            IntegrationItemResponse(
                provider_id="sms_outgoing",
                name="Outgoing SMS Reminder Webhook",
                category="sms",
                description="Delivers bill/EMI due reminders via an outbound HTTP webhook adapter for opted-in +91 numbers.",
                status=sms_out_status,  # type: ignore[arg-type]
                configured=sms_out_configured and sms_url_safe,
                connected=bool(settings.SMS_ENABLED and sms_out_configured and sms_url_safe),
                available=bool(settings.SMS_ENABLED and sms_out_configured and sms_url_safe),
                can_test=True,
                capabilities=["Opt-In Bill & EMI SMS Reminders", "SSRF-Validated Webhook Dispatch"],
                required_env_vars=(
                    []
                    if sms_out_configured
                    else ["SMS_ENABLED", "SMS_PROVIDER", "SMS_WEBHOOK_URL", "SMS_API_KEY", "SMS_SENDER_ID"]
                ),
                last_error=sms_out_err,
                safe_metadata={
                    "provider": settings.SMS_PROVIDER,
                    "sender_id": settings.SMS_SENDER_ID or "PFMIND",
                    "webhook_host": sms_domain or self._safe_host_from_url(settings.SMS_WEBHOOK_URL),
                },
            )
        )

        sms_in = get_sms_ingestion_provider().get_status()
        items.append(
            IntegrationItemResponse(
                provider_id="sms_ingestion",
                name="Incoming SMS Transaction Ingestion",
                category="sms",
                description=sms_in.limitation_reason,
                status="unavailable",
                configured=bool(sms_in.enabled),
                connected=False,
                available=bool(sms_in.available),
                can_test=True,
                capabilities=["Requires Explicit Consent Android Companion Bridge (Not Present)"],
                required_env_vars=["SMS_INGESTION_ENABLED", "SMS_INGESTION_PROVIDER"],
                last_error=sms_in.limitation_reason,
                safe_metadata={
                    "provider": sms_in.provider,
                    "supported_platforms_note": sms_in.supported_platforms_note,
                },
            )
        )

        # 4. AI Provider (Groq)
        groq_key_present = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip())
        groq_enabled = bool(settings.GROQ_ENABLED)
        groq_available = groq_enabled and groq_key_present
        groq_last_ts, groq_err = self._latest_groq_telemetry(db, user.id)
        if groq_available and groq_err:
            groq_status = "error"
        elif groq_available:
            groq_status = "connected"
        elif groq_key_present and not groq_enabled:
            groq_status = "configured_not_connected"
        else:
            groq_status = "unavailable"

        items.append(
            IntegrationItemResponse(
                provider_id="groq",
                name="Groq AI Inference",
                category="ai",
                description="Optional server-side LLM inference for transaction categorization, insight narration, and grounded AI Assistant synthesis (local deterministic engine runs when disabled).",
                status=groq_status,  # type: ignore[arg-type]
                configured=groq_key_present,
                connected=groq_available,
                available=groq_available,
                can_test=True,
                capabilities=[
                    "Grounded Assistant Response Synthesis",
                    "Optional Categorization Fallback",
                    "Insight Narrative Enrichment",
                ],
                required_env_vars=(
                    []
                    if groq_available
                    else ["GROQ_ENABLED", "GROQ_API_KEY", "GROQ_MODEL"]
                ),
                last_sync_or_test_at=groq_last_ts,
                last_error=groq_err,
                safe_metadata={
                    "enabled": groq_enabled,
                    "model_name": settings.GROQ_MODEL,
                    "timeout_seconds": settings.GROQ_TIMEOUT_SECONDS,
                    "fallback_mode": "Local deterministic rules & scikit-learn classifier",
                },
            )
        )

        # 5. Web Research Providers (LangSearch, Firecrawl, Tavily)
        for wp in list_provider_statuses():
            last_used_at, web_err = self._latest_web_telemetry(db, user.id, wp.provider)
            wp_status = (
                "error"
                if (wp.configured and web_err)
                else ("available" if wp.configured else "unavailable")
            )
            env_var = {
                "langsearch": "LANGSEARCH_API_KEY",
                "firecrawl": "FIRECRAWL_API_KEY",
                "tavily": "TAVILY_API_KEY",
            }.get(wp.provider, "")
            items.append(
                IntegrationItemResponse(
                    provider_id=wp.provider,
                    name=wp.display_name,
                    category="web_research",
                    description=wp.description,
                    status=wp_status,  # type: ignore[arg-type]
                    configured=wp.configured,
                    connected=wp.configured,
                    available=wp.configured,
                    is_preferred=(preferred_web == wp.provider),
                    can_test=True,
                    capabilities=[
                        "External Financial Web Search",
                        "Full-Text Page Retrieval" if wp.supports_full_text else "Snippet Search",
                        "No Silent Provider Fallback",
                    ],
                    required_env_vars=[] if wp.configured else [env_var],
                    last_sync_or_test_at=last_used_at,
                    last_error=web_err,
                    safe_metadata={
                        "supports_full_text": wp.supports_full_text,
                        "no_silent_fallback": True,
                        "selected_in_assistant": preferred_web == wp.provider,
                    },
                )
            )

        # 6. SMTP Email Delivery
        smtp_enabled = bool(settings.SMTP_ENABLED)
        smtp_configured = bool(smtp_enabled and settings.SMTP_HOST and settings.SMTP_PORT)
        items.append(
            IntegrationItemResponse(
                provider_id="smtp",
                name="SMTP Outbound Email",
                category="notifications",
                description="Transactional email delivery for account verification, password resets, and due bill/EMI notifications.",
                status="connected" if smtp_configured else "unavailable",
                configured=smtp_configured,
                connected=smtp_configured,
                available=smtp_configured,
                can_test=True,
                capabilities=[
                    "Account Verification & Password Reset Emails",
                    "Bill, Subscription & Loan EMI Email Reminders",
                ],
                required_env_vars=(
                    []
                    if smtp_configured
                    else ["SMTP_ENABLED", "SMTP_HOST", "SMTP_PORT", "SMTP_TLS", "EMAILS_FROM_EMAIL"]
                ),
                last_error=(
                    None
                    if smtp_configured
                    else "SMTP_ENABLED=false; emails are stored only in the development/test in-memory mailbox."
                ),
                safe_metadata={
                    "smtp_enabled": smtp_enabled,
                    "host": settings.SMTP_HOST if smtp_enabled else "disabled",
                    "port": settings.SMTP_PORT if smtp_enabled else None,
                    "tls_enabled": bool(settings.SMTP_TLS),
                    "sender_address": settings.EMAILS_FROM_EMAIL,
                    "auth_configured": bool(settings.SMTP_USER and settings.SMTP_PASSWORD),
                },
            )
        )

        return items, connections, preferred_web, web_enabled

    def get_overview(self, db: Session, user: User) -> IntegrationsOverviewResponse:
        items, connections, preferred_web, web_enabled = self._build_items_and_connections(db, user)
        non_planned = [i for i in items if not i.is_planned]
        return IntegrationsOverviewResponse(
            total_integrations=len(non_planned),
            configured_count=sum(1 for i in non_planned if i.configured),
            connected_count=sum(1 for i in non_planned if i.connected),
            unavailable_count=sum(1 for i in non_planned if not i.available),
            attention_required_count=sum(
                1 for i in non_planned if i.status in ("error", "configured_not_connected")
            ),
            planned_count=sum(1 for i in items if i.is_planned),
            preferred_web_provider=preferred_web,
            web_search_enabled=web_enabled,
            integrations=items,
            connections=connections,
        )

    def get_provider(self, db: Session, user: User, provider_id: str) -> IntegrationItemResponse:
        items, _, _, _ = self._build_items_and_connections(db, user)
        for item in items:
            if item.provider_id == provider_id:
                return item
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration provider '{provider_id}' not found.",
        )

    def list_providers(self, db: Session, user: User) -> list[IntegrationItemResponse]:
        items, _, _, _ = self._build_items_and_connections(db, user)
        return items

    def list_connections(self, db: Session, user: User) -> list[IntegrationConnectionSummary]:
        _, connections, _, _ = self._build_items_and_connections(db, user)
        return connections

    def get_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> IntegrationConnectionSummary:
        for conn in self.list_connections(db, user):
            if conn.connection_id == connection_id:
                return conn
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration connection not found.",
        )

    def disconnect_connection(
        self, db: Session, user: User, connection_id: uuid.UUID
    ) -> IntegrationDisconnectResponse:
        conn = self.get_connection(db, user, connection_id)
        if conn.connection_type == "banking":
            res = self.banking_service.disconnect_connection(db, user, connection_id)
            return IntegrationDisconnectResponse(
                connection_id=res.id,
                connection_type="banking",
                status=res.status,
                message="Banking connection disconnected. Historical accounts and ledger transactions are preserved.",
            )
        res_email = self.email_service.disconnect_gmail(db, user)
        return IntegrationDisconnectResponse(
            connection_id=connection_id,
            connection_type="email",
            status=res_email.status,
            message="Gmail OAuth disconnected and tokens removed. Historical ingested documents are preserved.",
        )

    def test_provider(self, db: Session, user: User, provider_id: str) -> IntegrationTestResponse:
        now = dt.datetime.now(dt.UTC)
        # Validate provider exists cleanly first (returns 404 for unknown provider IDs)
        provider_info = self.get_provider(db, user, provider_id)
        t0 = time.perf_counter()

        if provider_id in ("tavily", "langsearch", "firecrawl"):
            res = self.web_research_service.execute_search(
                provider_id=provider_id,
                query="RBI repo rate India",
                max_results=2,
                include_content=False,
                topic="finance",
            )
            elapsed = int((time.perf_counter() - t0) * 1000)
            if res.status in ("completed", "empty"):
                return IntegrationTestResponse(
                    provider_id=provider_id,
                    status="ok",
                    success=True,
                    message=f"{provider_info.name} responded cleanly ({len(res.sources)} search result(s)).",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={
                        "provider_status": res.status,
                        "result_count": len(res.sources),
                        "no_silent_fallback": True,
                    },
                )
            mapped = res.status if res.status in ("unavailable", "timeout", "rate_limited") else (
                "unavailable" if res.status == "unconfigured" else "error"
            )
            return IntegrationTestResponse(
                provider_id=provider_id,
                status=mapped,  # type: ignore[arg-type]
                success=False,
                message=res.error_message or f"{provider_info.name} check returned status '{res.status}'.",
                latency_ms=elapsed,
                checked_at=now,
                details={"provider_status": res.status, "no_silent_fallback": True},
            )

        if provider_id == "groq":
            groq = GroqAiProvider()
            if not groq.is_available():
                return IntegrationTestResponse(
                    provider_id="groq",
                    status="unavailable",
                    success=False,
                    message="Groq inference is disabled or GROQ_API_KEY is not configured. Local deterministic AI continues running.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                    details={"enabled": bool(settings.GROQ_ENABLED), "model": settings.GROQ_MODEL},
                )
            try:
                client = groq._get_client()
                completion = client.chat.completions.create(
                    model=groq.model_name,
                    temperature=0.0,
                    max_tokens=8,
                    messages=[{"role": "user", "content": "Reply with OK"}],
                )
                elapsed = int((time.perf_counter() - t0) * 1000)
                reply = (completion.choices[0].message.content or "").strip() if completion.choices else ""
                return IntegrationTestResponse(
                    provider_id="groq",
                    status="ok",
                    success=True,
                    message=f"Groq model '{groq.model_name}' responded successfully.",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={"model": groq.model_name, "sample_reply_present": bool(reply)},
                )
            except Exception as exc:
                elapsed = int((time.perf_counter() - t0) * 1000)
                return IntegrationTestResponse(
                    provider_id="groq",
                    status="error",
                    success=False,
                    message=f"Groq connectivity check failed ({type(exc).__name__}).",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={"model": groq.model_name},
                )

        if provider_id == "smtp":
            if not settings.SMTP_ENABLED:
                return IntegrationTestResponse(
                    provider_id="smtp",
                    status="unavailable",
                    success=False,
                    message="SMTP is disabled (SMTP_ENABLED=false). Configure SMTP_ENABLED=true, SMTP_HOST, and SMTP_PORT to dispatch live emails.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                    details={"smtp_enabled": False},
                )
            try:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=6) as server:
                    server.ehlo()
                    if settings.SMTP_TLS:
                        server.starttls()
                        server.ehlo()
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    code, _ = server.noop()
                elapsed = int((time.perf_counter() - t0) * 1000)
                return IntegrationTestResponse(
                    provider_id="smtp",
                    status="ok",
                    success=True,
                    message=f"SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} accepted connection (NOOP {code}).",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={"host": settings.SMTP_HOST, "port": settings.SMTP_PORT, "tls": settings.SMTP_TLS},
                )
            except Exception as exc:
                elapsed = int((time.perf_counter() - t0) * 1000)
                return IntegrationTestResponse(
                    provider_id="smtp",
                    status="error",
                    success=False,
                    message=f"SMTP handshake failed ({type(exc).__name__}).",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={"host": settings.SMTP_HOST, "port": settings.SMTP_PORT},
                )

        if provider_id == "gmail":
            conn = db.execute(
                select(EmailConnection).where(
                    EmailConnection.user_id == user.id,
                    EmailConnection.provider == "gmail",
                )
            ).scalar_one_or_none()
            if not self.email_service.adapter.is_configured():
                return IntegrationTestResponse(
                    provider_id="gmail",
                    status="unavailable",
                    success=False,
                    message="Google OAuth client credentials are not configured on the server.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                )
            if not conn or conn.status != "connected":
                return IntegrationTestResponse(
                    provider_id="gmail",
                    status="unavailable",
                    success=False,
                    message="Google OAuth is configured on the server, but your Gmail account is not connected yet.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                    details={"oauth_configured": True, "connected": False},
                )
            try:
                token = decrypt_oauth_token(conn.encrypted_access_token)
                elapsed = int((time.perf_counter() - t0) * 1000)
                if not token:
                    return IntegrationTestResponse(
                        provider_id="gmail",
                        status="error",
                        success=False,
                        message="Stored Gmail OAuth token could not be decrypted. Please reconnect Gmail.",
                        latency_ms=elapsed,
                        checked_at=now,
                    )
                return IntegrationTestResponse(
                    provider_id="gmail",
                    status="ok",
                    success=True,
                    message=f"Gmail connection active for {conn.email_address or 'authorized account'} with encrypted server-side tokens.",
                    latency_ms=elapsed,
                    checked_at=now,
                    details={"authorized_email": conn.email_address},
                )
            except Exception as exc:
                return IntegrationTestResponse(
                    provider_id="gmail",
                    status="error",
                    success=False,
                    message=f"Gmail token check failed ({type(exc).__name__}). Please reconnect Gmail.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                )

        if provider_id == "sms_outgoing":
            url_safe, _, domain = is_safe_public_url(settings.SMS_WEBHOOK_URL)
            if not settings.SMS_ENABLED or not sms_service.is_configured():
                return IntegrationTestResponse(
                    provider_id="sms_outgoing",
                    status="unavailable",
                    success=False,
                    message="Outgoing SMS reminders are disabled or missing SMS_WEBHOOK_URL / SMS_API_KEY.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                )
            if not url_safe:
                return IntegrationTestResponse(
                    provider_id="sms_outgoing",
                    status="error",
                    success=False,
                    message="Configured SMS_WEBHOOK_URL violates outbound SSRF security rules.",
                    latency_ms=int((time.perf_counter() - t0) * 1000),
                    checked_at=now,
                )
            return IntegrationTestResponse(
                provider_id="sms_outgoing",
                status="ok",
                success=True,
                message=f"SMS webhook configuration validated cleanly for host '{domain}'.",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                checked_at=now,
                details={"provider": settings.SMS_PROVIDER, "webhook_host": domain},
            )

        if provider_id == "demo_banking":
            conns = self.banking_service.list_user_connections(db, user)
            active = sum(1 for c in conns if c.status == "connected")
            return IntegrationTestResponse(
                provider_id="demo_banking",
                status="ok",
                success=True,
                message=f"Demo Banking Simulator ready ({len(get_all_demo_providers())} simulated institutions, {active} active connection(s)).",
                latency_ms=int((time.perf_counter() - t0) * 1000),
                checked_at=now,
                details={"active_connections": active, "simulated": True},
            )

        # sms_ingestion / account_aggregator
        return IntegrationTestResponse(
            provider_id=provider_id,
            status="unavailable",
            success=False,
            message=provider_info.description,
            latency_ms=int((time.perf_counter() - t0) * 1000),
            checked_at=now,
            details={"is_planned": provider_info.is_planned},
        )
