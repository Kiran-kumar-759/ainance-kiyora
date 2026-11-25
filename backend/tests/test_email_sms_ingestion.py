import datetime as dt
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal

import pymupdf
import pytest
from fastapi.testclient import TestClient
from googleapiclient.errors import HttpError
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.bills import Bill, BillReminder, Notification
from app.models.documents import (
    DocumentExtraction,
    DocumentLink,
    DocumentProcessingJob,
    DocumentReviewEvent,
    FinancialDocument,
)
from app.models.email_ingestion import (
    EmailAttachmentRecord,
    EmailConnection,
    EmailDocumentCandidate,
    EmailMessageRecord,
    EmailSyncHistory,
)
from app.models.user import User
from app.services.documents.doc_storage import PrivateDocumentStorage
from app.services.email.gmail_adapter import (
    EmailProviderAdapter,
    EmailSyncFetchResult,
    FetchedEmailAttachment,
    FetchedEmailMessage,
    OAuthTokenBundle,
)
from app.services.email.oauth_state import create_oauth_state, verify_oauth_state
from tests.conftest import TestingSessionLocal


class FakeGmailAdapter(EmailProviderAdapter):
    provider_name = "gmail"

    def __init__(self, *, configured: bool = True, raise_429: bool = False):
        self.configured = configured
        self.raise_429 = raise_429
        self.revoked = False

    def is_configured(self) -> bool:
        return self.configured

    def build_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        return f"https://accounts.google.com/o/oauth2/auth?state={state}&redirect_uri={redirect_uri}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokenBundle:
        return OAuthTokenBundle(
            access_token=f"ya29.mock-access-{code}",
            refresh_token="1//mock-refresh-secret",
            expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            email_address="kiran.india@gmail.com",
        )

    def refresh_tokens(self, *, access_token: str | None, refresh_token: str) -> OAuthTokenBundle:
        return OAuthTokenBundle(
            access_token="ya29.mock-refreshed",
            refresh_token=refresh_token,
            expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(hours=1),
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        )

    def revoke_token(self, token: str) -> bool:
        self.revoked = True
        return True

    def list_relevant_messages(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        query: str,
        max_results: int,
        last_history_id: str | None = None,
    ) -> EmailSyncFetchResult:
        if self.raise_429:
            class _Resp:
                status = 429
                reason = "Too Many Requests"

            raise HttpError(_Resp(), b"Rate Limit Exceeded")

        if last_history_id == "hist-100":
            return EmailSyncFetchResult(
                message_ids=["gmail-msg-2"],
                latest_history_id="hist-101",
                used_incremental_history=True,
            )
        return EmailSyncFetchResult(
            message_ids=["gmail-msg-1"],
            latest_history_id="hist-100",
            used_incremental_history=False,
        )

    def fetch_message(
        self, *, access_token: str, refresh_token: str | None, message_id: str
    ) -> FetchedEmailMessage:
        pdf = pymupdf.open()
        p = pdf.new_page()
        p.insert_text(
            (50, 72),
            "AIRTEL FIBER BROADBAND\nGSTIN: 07AABCB1234F1Z2\nInvoice No: AIR-771\n"
            "Invoice Date: 10/11/2026\nDue Date: 25/11/2026\nGrand Total: ₹999.00\n"
            if message_id == "gmail-msg-1"
            else "AIRTEL FIBER BROADBAND\nInvoice No: AIR-771\nInvoice Date: 10/11/2026\nGrand Total: ₹999.00\n",
            fontsize=11,
        )
        pdf_bytes = pdf.tobytes()
        pdf.close()

        return FetchedEmailMessage(
            provider_message_id=message_id,
            thread_id=f"thr-{message_id}",
            sender="ebill@airtel.in",
            subject="Your Airtel Fiber Monthly Invoice <script>alert(1)</script>",
            received_at=dt.datetime.now(dt.UTC),
            snippet_text="Airtel Fiber bill ₹999.00",
            body_text="Your monthly internet bill is attached.",
            history_id="hist-100",
            attachments=[
                FetchedEmailAttachment(
                    attachment_id=f"att-{message_id}",
                    filename=f"airtel_{message_id}.pdf",
                    content_type="application/pdf",
                    size=len(pdf_bytes),
                    data=pdf_bytes,
                )
            ],
        )

    def fetch_attachment(
        self, *, access_token: str, refresh_token: str | None, message_id: str, attachment_id: str
    ) -> bytes:
        return b""


@pytest.fixture
def live_email_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
    storage = PrivateDocumentStorage()
    cleanup = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                shutil.rmtree(storage.base_dir / str(user.id), ignore_errors=True)
                cleanup.execute(delete(EmailDocumentCandidate).where(EmailDocumentCandidate.user_id == user.id))
                cleanup.execute(delete(EmailAttachmentRecord).where(EmailAttachmentRecord.user_id == user.id))
                cleanup.execute(delete(EmailMessageRecord).where(EmailMessageRecord.user_id == user.id))
                cleanup.execute(delete(EmailSyncHistory).where(EmailSyncHistory.user_id == user.id))
                cleanup.execute(delete(EmailConnection).where(EmailConnection.user_id == user.id))
                cleanup.execute(delete(DocumentLink).where(DocumentLink.user_id == user.id))
                cleanup.execute(delete(DocumentReviewEvent).where(DocumentReviewEvent.user_id == user.id))
                cleanup.execute(delete(DocumentExtraction).where(DocumentExtraction.user_id == user.id))
                cleanup.execute(delete(DocumentProcessingJob).where(DocumentProcessingJob.user_id == user.id))
                cleanup.execute(delete(FinancialDocument).where(FinancialDocument.user_id == user.id))
                cleanup.execute(delete(Notification).where(Notification.user_id == user.id))
                cleanup.execute(delete(BillReminder).where(BillReminder.user_id == user.id))
                cleanup.execute(delete(Bill).where(Bill.user_id == user.id))
                cleanup.execute(delete(User).where(User.id == user.id))
        cleanup.commit()
    finally:
        cleanup.close()


def _login_user(tc: TestClient, created_emails: list[str], prefix: str) -> tuple[uuid.UUID, dict[str, str]]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    pw = "StrongPass#2026"
    r1 = tc.post("/api/v1/auth/register", json={"email": email, "password": pw, "full_name": prefix})
    assert r1.status_code in (200, 201)
    uid = uuid.UUID(r1.json()["user"]["id"])
    r2 = tc.post("/api/v1/auth/login", json={"email": email, "password": pw})
    csrf = r2.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return uid, {"X-CSRF-Token": csrf}


def test_gmail_oauth_encryption_incremental_sync_duplicates_and_sms_boundary(
    live_email_client, monkeypatch
):
    tc, created_emails = live_email_client
    user_id, headers = _login_user(tc, created_emails, "gmailuser")

    # Module D: Honest SMS Ingestion Boundary status check
    sms_res = tc.get("/api/v1/email/sms/status")
    assert sms_res.status_code == 200
    sms_json = sms_res.json()
    assert sms_json["available"] is False
    assert sms_json["enabled"] is False
    assert sms_json["outgoing_reminders_active"] is True

    # OAuth state integrity & cross-user rejection
    valid_state = create_oauth_state(user_id, settings.GOOGLE_OAUTH_REDIRECT_URI)
    assert verify_oauth_state(valid_state, user_id)["uid"] == str(user_id)
    with pytest.raises(ValueError):
        verify_oauth_state(valid_state, uuid.uuid4())
    with pytest.raises(ValueError):
        verify_oauth_state(valid_state + "tamper", user_id)

    # Inject FakeGmailAdapter cleanly into email route service
    from app.api.routes import email as email_routes

    fake_adapter = FakeGmailAdapter(configured=True)
    monkeypatch.setattr(email_routes.email_service, "adapter", fake_adapter)

    # Connect URL -> state validation -> callback token storage encrypted at rest
    conn_url = tc.get("/api/v1/email/gmail/connect")
    assert conn_url.status_code == 200
    state_tok = conn_url.json()["state"]
    assert conn_url.json()["scopes"] == ["https://www.googleapis.com/auth/gmail.readonly"]

    cb = tc.get(f"/api/v1/email/gmail/callback?code=authcode-1&state={state_tok}")
    assert cb.status_code == 200
    assert cb.json()["status"] == "connected"
    assert cb.json()["email_address"] == "kiran.india@gmail.com"
    assert "access_token" not in cb.text
    assert "refresh_token" not in cb.text

    # Verify DB token encryption
    db = TestingSessionLocal()
    try:
        conn_row = db.execute(
            select(EmailConnection).where(EmailConnection.user_id == user_id)
        ).scalar_one()
        assert conn_row.encrypted_access_token != "ya29.mock-access-authcode-1"
        assert "ya29.mock-access" not in (conn_row.encrypted_access_token or "")
    finally:
        db.close()

    # Initial sync (full_query -> historyId=hist-100)
    sync1 = tc.post("/api/v1/email/gmail/sync", headers=headers, json={})
    assert sync1.status_code == 200, sync1.text
    s1 = sync1.json()
    assert s1["sync_mode"] == "full_query"
    assert s1["attachments_processed"] == 1
    assert s1["candidates_needing_review"] == 1

    # Incremental sync (historyId=hist-100 -> hist-101) produces duplicate_warning instead of dropping
    sync2 = tc.post("/api/v1/email/gmail/sync", headers=headers, json={})
    assert sync2.status_code == 200
    s2 = sync2.json()
    assert s2["sync_mode"] == "incremental_history"
    assert s2["duplicate_candidates"] == 1

    cands = tc.get("/api/v1/email/candidates").json()
    assert len(cands) == 2
    assert cands[0]["status"] == "duplicate_warning"
    assert cands[1]["status"] == "needs_review"
    assert Decimal(str(cands[1]["amount"])) == Decimal("999.00")

    # Confirm email candidate -> creates unpaid bill ONLY after human confirm
    conf = tc.post(
        f"/api/v1/email/candidates/{cands[1]['id']}/confirm",
        headers=headers,
        json={"action": "create_bill", "bill_category": "internet"},
    )
    assert conf.status_code == 200, conf.text
    assert conf.json()["status"] == "confirmed"
    bills = tc.get("/api/v1/bills").json()["items"]
    assert len(bills) == 1
    assert bills[0]["derived_status"] != "paid"

    # Rate limit / 429 from Gmail handled cleanly
    fake_adapter.raise_429 = True
    sync_err = tc.post("/api/v1/email/gmail/sync", headers=headers, json={})
    assert sync_err.status_code == 429
    fake_adapter.raise_429 = False

    # Cross-user candidate isolation
    tc_other = TestClient(tc.app)
    _login_user(tc_other, created_emails, "othergmail")
    assert tc_other.get(f"/api/v1/email/candidates/{cands[0]['id']}").status_code == 404

    # Disconnect wipes encrypted tokens and revokes
    disc = tc.post("/api/v1/email/gmail/disconnect", headers=headers)
    assert disc.status_code == 200
    assert disc.json()["status"] == "disconnected"
    assert fake_adapter.revoked is True
