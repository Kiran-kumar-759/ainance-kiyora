import datetime as dt
import uuid
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.assistant import AiConversation, AiMessage, UserAiPreference
from app.models.auth import UserPreference, UserSession
from app.models.bills import Bill, BillReminder, Notification
from app.models.email_ingestion import EmailConnection, EmailSyncHistory
from app.models.finance import (
    BankingConnection,
    BankingSyncRun,
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.subscriptions import Subscription
from app.models.user import User
from app.services.bills.reminder_service import ReminderService
from app.services.email.token_crypto import encrypt_oauth_token
from app.services.web_research.schemas import WebSearchResponse
from tests.conftest import TestingSessionLocal


def _cleanup_users(emails: list[str]) -> None:
    if not emails:
        return
    with TestingSessionLocal() as db:
        users = db.execute(select(User).where(User.email.in_(emails))).scalars().all()
        uids = [u.id for u in users]
        if not uids:
            return
        db.execute(delete(EmailSyncHistory).where(EmailSyncHistory.user_id.in_(uids)))
        db.execute(delete(EmailConnection).where(EmailConnection.user_id.in_(uids)))
        db.execute(delete(BankingSyncRun).where(BankingSyncRun.user_id.in_(uids)))
        db.execute(delete(BankingConnection).where(BankingConnection.user_id.in_(uids)))
        db.execute(delete(AiMessage).where(AiMessage.user_id.in_(uids)))
        db.execute(delete(AiConversation).where(AiConversation.user_id.in_(uids)))
        db.execute(delete(UserAiPreference).where(UserAiPreference.user_id.in_(uids)))
        db.execute(delete(Notification).where(Notification.user_id.in_(uids)))
        db.execute(delete(BillReminder).where(BillReminder.user_id.in_(uids)))
        db.execute(delete(Subscription).where(Subscription.user_id.in_(uids)))
        db.execute(delete(Bill).where(Bill.user_id.in_(uids)))
        db.execute(
            delete(LedgerEntry).where(
                LedgerEntry.journal_id.in_(
                    select(LedgerJournal.id).where(LedgerJournal.user_id.in_(uids))
                )
            )
        )
        db.execute(delete(LedgerJournal).where(LedgerJournal.user_id.in_(uids)))
        db.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id.in_(uids)))
        db.execute(delete(FinancialAccount).where(FinancialAccount.user_id.in_(uids)))
        db.execute(delete(FinancialCategory).where(FinancialCategory.user_id.in_(uids)))
        db.execute(delete(UserPreference).where(UserPreference.user_id.in_(uids)))
        db.execute(delete(UserSession).where(UserSession.user_id.in_(uids)))
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


@pytest.fixture
def p12_app_and_users() -> Generator[tuple[object, list[str]], None, None]:
    created_emails: list[str] = []
    app = create_application()

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    rate_limiter._requests.clear()
    yield app, created_emails
    app.dependency_overrides.clear()
    _cleanup_users(created_emails)


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> tuple[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    reg = tc.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "InitialPassword123!", "full_name": f"{prefix} User"},
    )
    assert reg.status_code in (200, 201), reg.text
    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "InitialPassword123!"},
    )
    assert login.status_code == 200, login.text
    csrf_res = tc.get("/api/v1/auth/csrf")
    assert csrf_res.status_code == 200
    return email, csrf_res.json()["csrf_token"]


def test_integrations_overview_counts_and_secret_redaction(
    p12_app_and_users: tuple[object, list[str]],
    monkeypatch: pytest.MonkeyPatch,
):
    app, created_emails = p12_app_and_users
    monkeypatch.setattr(settings, "GROQ_ENABLED", True)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_super_secret_do_not_leak")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly_super_secret_do_not_leak")
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_USER", "smtp-user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "smtp_super_secret_do_not_leak")
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "SMS_PROVIDER", "webhook")
    monkeypatch.setattr(settings, "SMS_WEBHOOK_URL", "https://hooks.example.com/sms?token=sms_secret_tok")
    monkeypatch.setattr(settings, "SMS_API_KEY", "sms_super_secret_do_not_leak")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_ID", "google-client-id")
    monkeypatch.setattr(settings, "GOOGLE_OAUTH_CLIENT_SECRET", "oauth_super_secret_do_not_leak")

    with TestClient(app, raise_server_exceptions=False) as tc:
        assert tc.get("/api/v1/integrations/overview").status_code == 401
        _register_and_login(tc, created_emails, "integ_overview")

        res = tc.get("/api/v1/integrations/overview")
        assert res.status_code == 200, res.text
        raw_text = res.text
        for secret in (
            "gsk_super_secret_do_not_leak",
            "tvly_super_secret_do_not_leak",
            "smtp_super_secret_do_not_leak",
            "sms_super_secret_do_not_leak",
            "oauth_super_secret_do_not_leak",
            "sms_secret_tok",
        ):
            assert secret not in raw_text

        data = res.json()
        assert data["planned_count"] == 1
        assert data["total_integrations"] == 9
        by_id = {item["provider_id"]: item for item in data["integrations"]}
        assert by_id["account_aggregator"]["status"] == "planned"
        assert by_id["account_aggregator"]["is_planned"] is True
        assert by_id["demo_banking"]["available"] is True
        assert by_id["sms_ingestion"]["available"] is False
        assert by_id["gmail"]["status"] == "configured_not_connected"
        assert by_id["gmail"]["configured"] is True
        assert by_id["gmail"]["connected"] is False
        assert by_id["groq"]["connected"] is True
        assert by_id["smtp"]["connected"] is True
        assert by_id["tavily"]["available"] is True
        assert by_id["langsearch"]["available"] is False


def test_integrations_provider_tests_and_rate_limit(
    p12_app_and_users: tuple[object, list[str]],
    monkeypatch: pytest.MonkeyPatch,
):
    app, created_emails = p12_app_and_users
    with TestClient(app, raise_server_exceptions=False) as tc:
        _, csrf = _register_and_login(tc, created_emails, "integ_test")
        headers = {settings.CSRF_HEADER_NAME: csrf}

        # CSRF enforced on provider test
        assert tc.post("/api/v1/integrations/providers/tavily/test").status_code == 403
        # Unknown provider rejected with 404
        assert tc.post("/api/v1/integrations/providers/unknown_x/test", headers=headers).status_code == 404

        # Unconfigured Tavily returns honest unavailable (no silent fallback)
        r_unconf = tc.post("/api/v1/integrations/providers/tavily/test", headers=headers)
        assert r_unconf.status_code == 200
        assert r_unconf.json()["success"] is False
        assert r_unconf.json()["status"] == "unavailable"

        # Mocked LangSearch OK
        monkeypatch.setattr(
            "app.services.web_research.research_service.WebResearchService.execute_search",
            lambda self, **kw: WebSearchResponse(
                provider=kw["provider_id"],
                query=kw["query"],
                status="completed",
                sources=[],
                retrieved_at="2026-11-26T00:00:00Z",
            ),
        )
        r_ls = tc.post("/api/v1/integrations/providers/langsearch/test", headers=headers)
        assert r_ls.status_code == 200
        assert r_ls.json()["success"] is True
        assert r_ls.json()["details"]["no_silent_fallback"] is True

        # SMTP disabled returns honest unavailable
        monkeypatch.setattr(settings, "SMTP_ENABLED", False)
        r_smtp_off = tc.post("/api/v1/integrations/providers/smtp/test", headers=headers)
        assert r_smtp_off.status_code == 200
        assert r_smtp_off.json()["success"] is False
        assert r_smtp_off.json()["status"] == "unavailable"

        # Groq disabled returns honest unavailable
        monkeypatch.setattr(settings, "GROQ_ENABLED", False)
        r_groq_off = tc.post("/api/v1/integrations/providers/groq/test", headers=headers)
        assert r_groq_off.status_code == 200
        assert r_groq_off.json()["success"] is False

        # Mocked Groq OK
        fake_choice = MagicMock()
        fake_choice.message.content = "OK"
        fake_completion = MagicMock(choices=[fake_choice])
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = fake_completion
        monkeypatch.setattr(settings, "GROQ_ENABLED", True)
        monkeypatch.setattr(settings, "GROQ_API_KEY", "gsk_mock")
        monkeypatch.setattr("app.services.ai.groq_provider.GroqAiProvider._get_client", lambda self: fake_client)
        r_groq_ok = tc.post("/api/v1/integrations/providers/groq/test", headers=headers)
        assert r_groq_ok.status_code == 200
        assert r_groq_ok.json()["success"] is True

        # Trigger rate limit after 10 calls within 60s
        hit_429 = False
        for _ in range(8):
            resp = tc.post("/api/v1/integrations/providers/demo_banking/test", headers=headers)
            if resp.status_code == 429:
                hit_429 = True
                break
        assert hit_429 is True


def test_integrations_connections_ownership_and_disconnect_isolation(
    p12_app_and_users: tuple[object, list[str]],
    monkeypatch: pytest.MonkeyPatch,
):
    app, created_emails = p12_app_and_users
    monkeypatch.setattr(
        "app.services.email.gmail_adapter.GmailApiAdapter.revoke_token",
        lambda self, token: True,
    )

    with TestClient(app, raise_server_exceptions=False) as tc:
        alice_email, alice_csrf = _register_and_login(tc, created_emails, "alice_integ")
        alice_headers = {settings.CSRF_HEADER_NAME: alice_csrf}

        # Alice establishes Demo Bank connection & account
        bank_res = tc.post(
            "/api/v1/banking/connections/demo",
            headers=alice_headers,
            json={"provider_id": "demo_national_bank", "consent_given": True},
        )
        assert bank_res.status_code == 200, bank_res.text

        # Seed Alice's Gmail OAuth connection directly with Fernet encrypted tokens
        with TestingSessionLocal() as db:
            alice = db.execute(select(User).where(User.email == alice_email)).scalar_one()
            gmail_conn = EmailConnection(
                user_id=alice.id,
                provider="gmail",
                email_address="alice.finances@gmail.com",
                status="connected",
                scopes=["https://www.googleapis.com/auth/gmail.readonly"],
                encrypted_access_token=encrypt_oauth_token("secret-oauth-access-token"),
                encrypted_refresh_token=encrypt_oauth_token("secret-oauth-refresh-token"),
                token_expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
            )
            db.add(gmail_conn)
            db.commit()
            gmail_conn_id = str(gmail_conn.id)

        conns_res = tc.get("/api/v1/integrations/connections")
        assert conns_res.status_code == 200
        assert len(conns_res.json()) == 2
        assert "secret-oauth-access-token" not in conns_res.text
        assert "secret-oauth-refresh-token" not in conns_res.text

        # Switch to Bob -> cross-tenant access / disconnect must return 404
        tc.post("/api/v1/auth/logout", headers=alice_headers)
        _, bob_csrf = _register_and_login(tc, created_emails, "bob_integ")
        bob_headers = {settings.CSRF_HEADER_NAME: bob_csrf}
        assert tc.get(f"/api/v1/integrations/connections/{gmail_conn_id}").status_code == 404
        assert (
            tc.post(
                f"/api/v1/integrations/connections/{gmail_conn_id}/disconnect",
                headers=bob_headers,
            ).status_code
            == 404
        )
        tc.post("/api/v1/auth/logout", headers=bob_headers)

        # Log back in as Alice and disconnect Gmail cleanly
        relogin = tc.post(
            "/api/v1/auth/login",
            json={"email": alice_email, "password": "InitialPassword123!"},
        )
        assert relogin.status_code == 200
        alice_csrf_2 = tc.get("/api/v1/auth/csrf").json()["csrf_token"]
        disc = tc.post(
            f"/api/v1/integrations/connections/{gmail_conn_id}/disconnect",
            headers={settings.CSRF_HEADER_NAME: alice_csrf_2},
        )
        assert disc.status_code == 200
        assert disc.json()["status"] == "disconnected"

        with TestingSessionLocal() as db:
            row = db.get(EmailConnection, uuid.UUID(gmail_conn_id))
            assert row is not None
            assert row.status == "disconnected"
            assert row.encrypted_access_token is None
            assert row.encrypted_refresh_token is None


def test_settings_profile_change_password_and_session_revocation(
    p12_app_and_users: tuple[object, list[str]],
):
    app, created_emails = p12_app_and_users
    with TestClient(app, raise_server_exceptions=False) as tc1, TestClient(
        app, raise_server_exceptions=False
    ) as tc2:
        email, csrf1 = _register_and_login(tc1, created_emails, "sec_settings")
        headers1 = {settings.CSRF_HEADER_NAME: csrf1}

        # Second device session
        l2 = tc2.post("/api/v1/auth/login", json={"email": email, "password": "InitialPassword123!"})
        assert l2.status_code == 200
        assert tc2.get("/api/v1/auth/me").status_code == 200

        assert len(tc1.get("/api/v1/auth/sessions").json()) == 2

        # Wrong current password rejected
        bad = tc1.post(
            "/api/v1/auth/change-password",
            headers=headers1,
            json={
                "current_password": "WrongPassword!",
                "new_password": "RotatedPassword456!",
                "revoke_other_sessions": True,
            },
        )
        assert bad.status_code == 400

        # Valid change password rotates hash and revokes Browser 2 session while preserving Browser 1
        ok = tc1.post(
            "/api/v1/auth/change-password",
            headers=headers1,
            json={
                "current_password": "InitialPassword123!",
                "new_password": "RotatedPassword456!",
                "revoke_other_sessions": True,
            },
        )
        assert ok.status_code == 200, ok.text
        assert tc1.get("/api/v1/auth/me").status_code == 200
        assert tc2.get("/api/v1/auth/me").status_code == 401
        assert len(tc1.get("/api/v1/auth/sessions").json()) == 1

        # Verify new password works and old fails
        assert (
            tc2.post("/api/v1/auth/login", json={"email": email, "password": "InitialPassword123!"}).status_code
            == 401
        )
        assert (
            tc2.post("/api/v1/auth/login", json={"email": email, "password": "RotatedPassword456!"}).status_code
            == 200
        )


def test_settings_preferences_reminders_ai_provider_and_privacy_summary(
    p12_app_and_users: tuple[object, list[str]],
):
    app, created_emails = p12_app_and_users
    with TestClient(app, raise_server_exceptions=False) as tc:
        email, csrf = _register_and_login(tc, created_emails, "prefs_p12")
        headers = {settings.CSRF_HEADER_NAME: csrf}

        # Update partial localization, notification & application settings
        up_res = tc.patch(
            "/api/v1/users/me/preferences",
            headers=headers,
            json={
                "preferred_currency": "INR",
                "locale": "en-IN",
                "timezone": "Asia/Kolkata",
                "date_format": "DD/MM/YYYY",
                "notification_preferences": {
                    "subscription_reminders": False,
                    "week_start": "sunday",
                    "compact_sidebar": True,
                    "default_landing_view": "analytics",
                },
            },
        )
        assert up_res.status_code == 200, up_res.text
        np = up_res.json()["notification_preferences"]
        assert np["subscription_reminders"] is False
        assert np["bill_reminders"] is True  # preserved default
        assert np["compact_sidebar"] is True
        assert np["default_landing_view"] == "analytics"
        assert np["week_start"] == "sunday"

        # Update Phase 10 AI preference and verify Integrations overview reflects it cleanly
        ai_res = tc.patch(
            "/api/v1/assistant/preferences",
            headers=headers,
            json={"default_web_provider": "langsearch", "web_search_enabled": False},
        )
        assert ai_res.status_code == 200
        ov_res = tc.get("/api/v1/integrations/overview").json()
        assert ov_res["preferred_web_provider"] == "langsearch"
        assert ov_res["web_search_enabled"] is False
        ls_card = [i for i in ov_res["integrations"] if i["provider_id"] == "langsearch"][0]
        assert ls_card["is_preferred"] is True

        # Create a subscription & test that muted subscription_reminders skips notification
        # WITHOUT deleting the underlying subscription commitment
        sub_res = tc.post(
            "/api/v1/subscriptions",
            headers=headers,
            json={
                "subscription_name": "Hotstar Annual",
                "provider_name": "Disney+ Hotstar",
                "amount": "1499.00",
                "billing_frequency": "yearly",
                "start_date": dt.date.today().isoformat(),
                "next_renewal_date": (dt.date.today() + dt.timedelta(days=1)).isoformat(),
                "reminder_enabled": True,
                "reminder_days_before": [1, 0],
            },
        )
        assert sub_res.status_code == 201, sub_res.text
        sub_id = uuid.UUID(sub_res.json()["id"])

        with TestingSessionLocal() as db:
            user = db.execute(select(User).where(User.email == email)).scalar_one()
            rems = db.execute(
                select(BillReminder).where(BillReminder.subscription_id == sub_id)
            ).scalars().all()
            assert len(rems) >= 1
            for rem in rems:
                rem.reminder_at = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)
            db.commit()
            processed = ReminderService().process_due_reminders(db, user_id=user.id)
            assert processed.unavailable_count >= 1
            # Subscription still exists & active
            sub_after = db.get(Subscription, sub_id)
            assert sub_after is not None and sub_after.status == "active"

        # Verify Privacy & Data summary reflects real DB counts
        priv = tc.get("/api/v1/users/me/privacy-summary")
        assert priv.status_code == 200
        priv_data = priv.json()
        assert priv_data["subscriptions_count"] == 1
        assert priv_data["account_deletion_status"] == "deferred"
        assert len(priv_data["export_endpoints"]) == 3
