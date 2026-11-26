import datetime as dt
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.assistant import AiConversation, AiMessage, DocumentRagChunk, UserAiPreference
from app.models.bills import Bill, BillReminder, Notification
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.subscriptions import Subscription
from app.models.user import User
from app.services.ai.groq_provider import GroqAiProvider
from app.services.web_research.research_service import WebResearchService
from app.services.web_research.schemas import NormalizedWebSource, WebSearchResponse
from tests.conftest import TestingSessionLocal


@pytest.fixture
def assistant_api_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, created_emails

    app.dependency_overrides.clear()
    with TestingSessionLocal() as cleanup_db:
        if created_emails:
            users = cleanup_db.execute(
                select(User).where(User.email.in_(created_emails))
            ).scalars().all()
            uids = [u.id for u in users]
            if uids:
                cleanup_db.execute(delete(AiMessage).where(AiMessage.user_id.in_(uids)))
                cleanup_db.execute(delete(AiConversation).where(AiConversation.user_id.in_(uids)))
                cleanup_db.execute(delete(UserAiPreference).where(UserAiPreference.user_id.in_(uids)))
                cleanup_db.execute(delete(DocumentRagChunk).where(DocumentRagChunk.user_id.in_(uids)))
                cleanup_db.execute(delete(Notification).where(Notification.user_id.in_(uids)))
                cleanup_db.execute(delete(BillReminder).where(BillReminder.user_id.in_(uids)))
                cleanup_db.execute(delete(Subscription).where(Subscription.user_id.in_(uids)))
                cleanup_db.execute(delete(Bill).where(Bill.user_id.in_(uids)))
                cleanup_db.execute(
                    delete(LedgerEntry).where(
                        LedgerEntry.journal_id.in_(
                            select(LedgerJournal.id).where(LedgerJournal.user_id.in_(uids))
                        )
                    )
                )
                cleanup_db.execute(delete(LedgerJournal).where(LedgerJournal.user_id.in_(uids)))
                cleanup_db.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id.in_(uids)))
                cleanup_db.execute(delete(FinancialAccount).where(FinancialAccount.user_id.in_(uids)))
                cleanup_db.execute(delete(FinancialCategory).where(FinancialCategory.user_id.in_(uids)))
                cleanup_db.execute(delete(User).where(User.id.in_(uids)))
                cleanup_db.commit()


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> str:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    created_emails.append(email)
    reg = tc.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": f"{prefix} User"},
    )
    assert reg.status_code in (200, 201), reg.text
    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    csrf = login.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return csrf


def test_assistant_auth_and_csrf_guards(assistant_api_client):
    tc, created_emails = assistant_api_client
    assert tc.get("/api/v1/assistant/providers").status_code == 401
    assert tc.get("/api/v1/assistant/conversations").status_code == 401

    csrf = _register_and_login(tc, created_emails, "asst_sec")
    # Mutation without CSRF header fails
    no_csrf = tc.post("/api/v1/assistant/conversations", json={"title": "Test"})
    assert no_csrf.status_code == 403

    with_csrf = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Test"},
        headers={"X-CSRF-Token": csrf},
    )
    assert with_csrf.status_code == 201


def test_preferences_conversations_and_cross_user_isolation(assistant_api_client):
    tc, created_emails = assistant_api_client
    csrf_a = _register_and_login(tc, created_emails, "asst_a")

    # Providers list has exact 3 Phase 10 providers
    provs = tc.get("/api/v1/assistant/providers").json()
    assert {p["provider"] for p in provs} == {"langsearch", "firecrawl", "tavily"}

    # Update preferences -> persists across GET
    upd_pref = tc.patch(
        "/api/v1/assistant/preferences",
        json={
            "default_web_provider": "firecrawl",
            "web_search_enabled": False,
            "voice_read_aloud_enabled": True,
        },
        headers={"X-CSRF-Token": csrf_a},
    )
    assert upd_pref.status_code == 200
    assert upd_pref.json()["default_web_provider"] == "firecrawl"
    assert upd_pref.json()["web_search_enabled"] is False
    assert upd_pref.json()["voice_read_aloud_enabled"] is True

    # Create & rename conversation
    conv = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Initial Chat"},
        headers={"X-CSRF-Token": csrf_a},
    ).json()
    conv_id = conv["id"]

    ren = tc.patch(
        f"/api/v1/assistant/conversations/{conv_id}",
        json={"title": "Renamed Budget Chat"},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert ren.status_code == 200
    assert ren.json()["title"] == "Renamed Budget Chat"

    # Switch to User B -> cannot read/modify/delete User A's conversation
    csrf_b = _register_and_login(tc, created_emails, "asst_b")
    assert tc.get(f"/api/v1/assistant/conversations/{conv_id}").status_code == 404
    assert (
        tc.post(
            f"/api/v1/assistant/conversations/{conv_id}/messages",
            json={"content": "hello"},
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )
    assert (
        tc.delete(
            f"/api/v1/assistant/conversations/{conv_id}",
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )


def test_personal_finance_tools_citations_and_no_private_leak_in_web_query(
    assistant_api_client, monkeypatch
):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "asst_fin")

    # Seed bank account, Food category, and a transaction via real APIs
    acc = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "HDFC Savings Main",
            "account_type": "savings",
            "opening_balance": "75000.00",
            "currency": "INR",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert acc.status_code in (200, 201), acc.text
    acc_id = acc.json()["id"]

    cats = tc.get("/api/v1/finance/categories?category_type=expense").json()
    food_cat = next((c for c in cats if "food" in c["name"].lower()), cats[0])

    tx = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": acc_id,
            "transaction_type": "expense",
            "amount": "1250.00",
            "currency": "INR",
            "category_id": food_cat["id"],
            "description": "Swiggy Family Dinner",
            "merchant_payee": "Swiggy",
            "transaction_date": dt.date.today().isoformat(),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert tx.status_code in (200, 201), tx.text

    conv = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Spending Analysis", "web_search_enabled": False},
        headers={"X-CSRF-Token": csrf},
    ).json()

    # Personal spending question without web search -> deterministic personal evidence, zero web calls
    captured_search_queries: list[str] = []

    def _mock_search(self, *, provider_id, query, max_results=5, include_content=True, topic="finance"):
        captured_search_queries.append(f"{provider_id}:{query}")
        return WebSearchResponse(
            provider=provider_id,
            query=query,
            status="completed",
            retrieved_at="2026-11-25T10:00:00+00:00",
            sources=[
                NormalizedWebSource(
                    citation_id=1,
                    provider=provider_id,
                    title="RBI Master Direction on Digital Payments",
                    url="https://www.rbi.org.in/commonman/English/Scripts/Notification.aspx",
                    domain="www.rbi.org.in",
                    snippet="UPI transaction limits and safety guidelines.",
                    retrieved_at="2026-11-25T10:00:00+00:00",
                    content_available=False,
                )
            ],
        )

    monkeypatch.setattr(WebResearchService, "execute_search", _mock_search)

    msg_personal = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "How much is my account balance and how much did I spend this month?",
            "web_search_enabled": False,
            "include_personal_context": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert msg_personal.status_code == 200, msg_personal.text
    body = msg_personal.json()
    assert body["web_search_used"] is False
    assert captured_search_queries == []
    assert "get_account_balances" in body["tools_invoked"]
    assert "get_spending_summary" in body["tools_invoked"]
    assert len(body["evidence_items"]) >= 2
    assert any("73,750.00" in e["summary"] or "HDFC Savings Main" in e["title"] for e in body["evidence_items"])

    # Casual greeting ("Hi") even with web_search_enabled=True must NOT trigger web search or tool dump
    msg_hi = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "Hi",
            "web_search_enabled": True,
            "web_provider": "tavily",
            "include_personal_context": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert msg_hi.status_code == 200, msg_hi.text
    hi_body = msg_hi.json()
    assert hi_body["web_search_used"] is False
    assert hi_body["tools_invoked"] == []
    assert captured_search_queries == []

    # Mock Groq returning fullwidth 【1】 citation & fake 【99】 citation -> normalized & invalid stripped
    monkeypatch.setattr(GroqAiProvider, "is_available", lambda self: True)

    class _FakeMsg:
        content = "Per RBI guidelines 【1】 and your HDFC balance [2], note fake citation 【99】."

    class _FakeChoice:
        message = _FakeMsg()

    class _FakeCompletion:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeCompletion()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    monkeypatch.setattr(GroqAiProvider, "_get_client", lambda self: _FakeClient())

    msg_web = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "What are the latest RBI rules on UPI limits and compare with my balance?",
            "web_search_enabled": True,
            "web_provider": "tavily",
            "include_personal_context": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert msg_web.status_code == 200, msg_web.text
    wbody = msg_web.json()
    assert wbody["web_search_used"] is True
    assert wbody["provider_used"] == "tavily"
    assert "[99]" not in wbody["content"]
    assert "【99】" not in wbody["content"]
    assert "[1]" in wbody["content"]
    # Ensure personal balance INR 73750 was NEVER leaked into web query string
    assert captured_search_queries
    assert "73750" not in captured_search_queries[0]
    assert "HDFC Savings Main" not in captured_search_queries[0]

    # Web follow-up phrase ("yes search in web") triggers web_research using previous topic
    captured_search_queries.clear()
    followup_web = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "What are JioHotstar plan prices?",
            "web_search_enabled": True,
            "web_provider": "tavily",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert followup_web.status_code == 200
    assert followup_web.json()["web_search_used"] is True

    captured_search_queries.clear()
    confirm_web = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "yes search in web",
            "web_search_enabled": True,
            "web_provider": "tavily",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert confirm_web.status_code == 200
    assert confirm_web.json()["web_search_used"] is True
    assert captured_search_queries and "jiohotstar" in captured_search_queries[0].lower()


def test_voice_parse_expense_requires_confirmation_and_does_not_write_ledger(assistant_api_client):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "voice_u")

    acc = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "ICICI Salary",
            "account_type": "savings",
            "opening_balance": "50000.00",
            "currency": "INR",
        },
        headers={"X-CSRF-Token": csrf},
    ).json()

    tx_before = tc.get("/api/v1/finance/transactions").json()["total"]

    res = tc.post(
        "/api/v1/assistant/voice/parse-expense",
        json={"transcript": "Spent 450 rupees on Swiggy lunch today"},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200, res.text
    draft = res.json()
    assert Decimal(str(draft["amount"])) == Decimal("450.00")
    assert draft["transaction_type"] == "expense"
    assert draft["requires_user_confirmation"] is True
    assert draft["account_id"] is None
    assert "account_id" in draft["missing_fields"]
    assert "lunch" in (draft["description"] or "").lower()

    named_acc_draft = tc.post(
        "/api/v1/assistant/voice/parse-expense",
        json={"transcript": "Paid 450 rupees on Swiggy lunch using ICICI Salary"},
        headers={"X-CSRF-Token": csrf},
    ).json()
    assert named_acc_draft["account_id"] == acc["id"]

    # Missing amount case leaves amount null and adds to missing_fields cleanly
    ambiguous = tc.post(
        "/api/v1/assistant/voice/parse-expense",
        json={"transcript": "Bought some coffee with friends"},
        headers={"X-CSRF-Token": csrf},
    ).json()
    assert ambiguous["amount"] is None
    assert "amount" in ambiguous["missing_fields"]

    # Ledger must remain untouched until user confirms in UI!
    tx_after = tc.get("/api/v1/finance/transactions").json()["total"]
    assert tx_after == tx_before


def test_voice_transcribe_and_speak_endpoints(assistant_api_client, monkeypatch):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "voice_tts")

    # 1. /voice/speak produces valid WAV audio via espeak-ng
    speak_res = tc.post(
        "/api/v1/assistant/voice/speak",
        json={"text": "Your monthly food expense is 1250 rupees."},
        headers={"X-CSRF-Token": csrf},
    )
    assert speak_res.status_code == 200, speak_res.text
    assert speak_res.headers["content-type"].startswith("audio/wav")
    assert speak_res.content[:4] == b"RIFF"

    # 2. /voice/transcribe returns 503 when Groq is disabled (test default)
    stt_off = tc.post(
        "/api/v1/assistant/voice/transcribe",
        files={"audio": ("mic.webm", b"OggS" + b"\x00" * 128, "audio/webm")},
        headers={"X-CSRF-Token": csrf},
    )
    assert stt_off.status_code == 503

    # 3. /voice/transcribe succeeds with mocked Groq Whisper client
    monkeypatch.setattr(GroqAiProvider, "is_available", lambda self: True)

    class _FakeTranscription:
        text = "Spent 450 rupees on Swiggy lunch"

    class _FakeTranscriptions:
        def create(self, **kwargs):
            return _FakeTranscription()

    class _FakeAudio:
        transcriptions = _FakeTranscriptions()

    class _FakeWhisperClient:
        audio = _FakeAudio()

    monkeypatch.setattr(GroqAiProvider, "_get_client", lambda self: _FakeWhisperClient())

    stt_on = tc.post(
        "/api/v1/assistant/voice/transcribe",
        files={"audio": ("mic.webm", b"WEBM" + b"\x00" * 128, "audio/webm")},
        headers={"X-CSRF-Token": csrf},
    )
    assert stt_on.status_code == 200, stt_on.text
    assert stt_on.json()["transcript"] == "Spent 450 rupees on Swiggy lunch"
    assert stt_on.json()["provider"] == "groq:whisper-large-v3-turbo"


def test_chat_bill_action_draft_and_no_unconfirmed_bill_write(assistant_api_client):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "bill_chat")

    conv = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Bill Commands", "web_search_enabled": True},
        headers={"X-CSRF-Token": csrf},
    ).json()

    bills_before = tc.get("/api/v1/bills").json()["total"]

    res = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "Add an electricity bill of 1,200 rupees due next week",
            "web_search_enabled": True,
            "web_provider": "tavily",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["web_search_used"] is False
    draft = body["draft_action"]
    assert draft is not None
    assert draft["action_type"] == "create_bill"
    assert draft["bill_category"] == "electricity"
    assert Decimal(str(draft["expected_amount"])) == Decimal("1200.00")
    assert draft["requires_user_confirmation"] is True

    # Must NOT write to Bills automatically until user clicks Confirm & Add Bill
    bills_after = tc.get("/api/v1/bills").json()["total"]
    assert bills_after == bills_before

    # Confirming through /messages/{id}/confirm-action persists execution_status='executed' and blocks duplicates
    confirm_res = tc.post(
        f"/api/v1/assistant/messages/{body['id']}/confirm-action",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert confirm_res.status_code == 200, confirm_res.text
    confirmed_msg = confirm_res.json()
    assert confirmed_msg["draft_action"]["execution_status"] == "executed"
    assert confirmed_msg["draft_action"]["requires_user_confirmation"] is False
    assert tc.get("/api/v1/bills").json()["total"] == bills_before + 1

    # Reloading conversation preserves execution_status='executed', and re-confirming returns 409 Conflict (no duplicate!)
    reloaded = tc.get(f"/api/v1/assistant/conversations/{conv['id']}").json()
    saved_msg = next(m for m in reloaded["messages"] if m["id"] == body["id"])
    assert saved_msg["draft_action"]["execution_status"] == "executed"

    dup_res = tc.post(
        f"/api/v1/assistant/messages/{body['id']}/confirm-action",
        json={},
        headers={"X-CSRF-Token": csrf},
    )
    assert dup_res.status_code == 409
    assert tc.get("/api/v1/bills").json()["total"] == bills_before + 1


def test_auto_execute_toggle_creates_bills_and_ott_subscriptions_automatically(assistant_api_client):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "auto_exec")

    pref_res = tc.patch(
        "/api/v1/assistant/preferences",
        json={"auto_execute_actions": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert pref_res.status_code == 200
    assert pref_res.json()["auto_execute_actions"] is True

    conv = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Auto Actions", "web_search_enabled": False},
        headers={"X-CSRF-Token": csrf},
    ).json()

    # 1. Auto-create an OTT Subscription directly from chat command
    sub_msg = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={"content": "Add a Netflix subscription of 649 per month"},
        headers={"X-CSRF-Token": csrf},
    )
    assert sub_msg.status_code == 200, sub_msg.text
    sbody = sub_msg.json()
    assert sbody["draft_action"]["action_type"] == "create_subscription"
    assert sbody["draft_action"]["execution_status"] == "executed"
    assert sbody["draft_action"]["execution_mode"] == "auto"
    assert "Netflix" in sbody["draft_action"]["executed_label"]

    subs = tc.get("/api/v1/subscriptions").json()
    assert subs["total"] == 1
    assert subs["items"][0]["subscription_name"] == "Netflix"

    # 2. Auto-create a Bill directly from chat command using persisted auto_execute_actions preference
    bill_msg = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={"content": "Add a water bill of 500 rupees due tomorrow"},
        headers={"X-CSRF-Token": csrf},
    )
    assert bill_msg.status_code == 200, bill_msg.text
    bbody = bill_msg.json()
    assert bbody["draft_action"]["action_type"] == "create_bill"
    assert bbody["draft_action"]["execution_status"] == "executed"
    assert bbody["draft_action"]["execution_mode"] == "auto"
    assert tc.get("/api/v1/bills").json()["total"] == 1


def test_hybrid_purchase_affordability_uses_internal_pg_and_web_and_asks_clarifying_questions(
    assistant_api_client, monkeypatch
):
    tc, created_emails = assistant_api_client
    csrf = _register_and_login(tc, created_emails, "hybrid_buy")

    # Seed internal PostgreSQL account + upcoming bill
    acc_res = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "HDFC Wealth Savings",
            "account_type": "savings",
            "opening_balance": "240000.00",
            "currency": "INR",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert acc_res.status_code in (200, 201), acc_res.text

    bill_res = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Society Maintenance",
            "bill_category": "maintenance",
            "bill_type": "one_time",
            "expected_amount": "3500.00",
            "due_date": (dt.date.today() + dt.timedelta(days=5)).isoformat(),
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert bill_res.status_code in (200, 201), bill_res.text

    captured_web_queries: list[str] = []

    def _mock_product_search(
        self, *, provider_id, query, max_results=5, include_content=True, topic="finance"
    ):
        captured_web_queries.append(query)
        return WebSearchResponse(
            provider=provider_id,
            query=query,
            status="completed",
            retrieved_at="2026-11-26T12:00:00+00:00",
            sources=[
                NormalizedWebSource(
                    citation_id=1,
                    provider=provider_id,
                    title="Sony Bravia & Apple MacBook India Pricing",
                    url="https://www.apple.com/in/shop/buy-mac",
                    domain="www.apple.com",
                    snippet="Apple MacBook Air M3 starts around ₹99,900 - ₹1,14,900 in India; Sony Bravia 4K LED TVs range ₹45,000 - ₹1,40,000.",
                    retrieved_at="2026-11-26T12:00:00+00:00",
                    content_available=False,
                )
            ],
        )

    monkeypatch.setattr(WebResearchService, "execute_search", _mock_product_search)

    conv = tc.post(
        "/api/v1/assistant/conversations",
        json={"title": "Laptop & TV Affordability", "web_search_enabled": True},
        headers={"X-CSRF-Token": csrf},
    ).json()

    # Case 1: Deterministic fallback mode checks both PostgreSQL balances & Web search + clarifying questions
    monkeypatch.setattr(GroqAiProvider, "is_available", lambda self: False)
    r1 = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "Can I afford an Apple MacBook laptop of price 100000 or 1 lakh?",
            "web_search_enabled": True,
            "web_provider": "tavily",
            "include_personal_context": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["web_search_used"] is True
    assert "get_account_balances" in b1["tools_invoked"]
    assert "get_spending_summary" in b1["tools_invoked"]
    assert "get_upcoming_commitments" in b1["tools_invoked"]
    assert "get_forecast_and_insights" in b1["tools_invoked"]
    assert "web_research:tavily" in b1["tools_invoked"]

    origins = {e["origin"] for e in b1["evidence_items"]}
    assert "personal_financial_record" in origins
    assert "external_web" in origins
    assert "240,000.00" in b1["content"]
    assert "Quick Questions to Tailor This Better" in b1["content"]
    assert "HDFC Wealth Savings" not in captured_web_queries[0]
    assert "240000" not in captured_web_queries[0]

    # Case 2: Open purchase question ("can I buy a sony TV?") runs internal tools + web research cleanly
    captured_web_queries.clear()
    r2 = tc.post(
        f"/api/v1/assistant/conversations/{conv['id']}/messages",
        json={
            "content": "can I buy a sony TV?",
            "web_search_enabled": True,
            "web_provider": "tavily",
            "include_personal_context": True,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 200, r2.text
    b2 = r2.json()
    assert b2["web_search_used"] is True
    assert "get_account_balances" in b2["tools_invoked"]
    assert "web_research:tavily" in b2["tools_invoked"]
    assert captured_web_queries and "sony tv" in captured_web_queries[0].lower()
    assert "Quick Questions to Tailor This Better" in b2["content"]
