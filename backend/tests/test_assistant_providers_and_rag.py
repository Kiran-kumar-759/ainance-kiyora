import datetime as dt
import uuid
from collections.abc import Generator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.assistant import DocumentRagChunk
from app.models.documents import DocumentExtraction, FinancialDocument
from app.models.user import User
from app.services.assistant.rag_service import (
    purge_document_chunks,
    reindex_user_documents,
    retrieve_personal_documents,
)
from app.services.web_research.firecrawl_provider import FirecrawlProvider
from app.services.web_research.langsearch_provider import LangSearchProvider
from app.services.web_research.research_service import (
    WebResearchService,
    sanitize_public_search_query,
)
from app.services.web_research.schemas import WebSearchRequest
from app.services.web_research.source_validation import is_safe_public_url
from app.services.web_research.tavily_provider import TavilyProvider
from tests.conftest import TestingSessionLocal


@pytest.fixture
def rag_api_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
                cleanup_db.execute(delete(DocumentRagChunk).where(DocumentRagChunk.user_id.in_(uids)))
                cleanup_db.execute(delete(FinancialDocument).where(FinancialDocument.user_id.in_(uids)))
                cleanup_db.execute(delete(User).where(User.id.in_(uids)))
                cleanup_db.commit()


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> tuple[str, User]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    created_emails.append(email)
    reg = tc.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Password123!", "full_name": f"{prefix} User"},
    )
    assert reg.status_code in (200, 201), reg.text
    csrf = tc.cookies.get("pfm_csrf_token", "")
    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
        headers={"X-CSRF-Token": csrf} if csrf else {},
    )
    assert login.status_code == 200, login.text
    csrf = tc.cookies.get("pfm_csrf_token", "") or csrf
    with TestingSessionLocal() as db:
        user = db.execute(select(User).where(User.email == email)).scalar_one()
        return csrf, user


class _MockResponse:
    def __init__(self, status_code: int, payload: object):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_ssrf_and_pii_query_sanitization():
    for bad in [
        "http://localhost:8000/secret",
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/internal",
        "http://192.168.1.10/router",
        "ftp://rbi.org.in/file",
        "javascript:alert(1)",
        "http://service.internal/api",
    ]:
        ok, _, _ = is_safe_public_url(bad)
        assert not ok, f"Expected SSRF/unsafe rejection for {bad}"

    ok, clean, domain = is_safe_public_url("https://www.rbi.org.in/Scripts/FAQView.aspx?Id=158")
    assert ok
    assert domain == "www.rbi.org.in"
    assert clean.startswith("https://www.rbi.org.in/")

    sanitized = sanitize_public_search_query(
        "My account 123456789012 and user@example.com want latest RBI UPI limits"
    )
    assert "123456789012" not in sanitized
    assert "user@example.com" not in sanitized
    assert "RBI UPI limits" in sanitized


def test_tavily_provider_success_and_error_states(monkeypatch):
    req = WebSearchRequest(query="RBI UPI limit 2026", max_results=3, include_content=True, topic="finance")

    # 1. Missing key -> unconfigured
    unconfigured = TavilyProvider(api_key="").search(req)
    assert unconfigured.status == "unconfigured"
    assert "not configured" in (unconfigured.error_message or "").lower()

    # 2. Success with unsafe URL filtered out
    class _ClientOk:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            return _MockResponse(
                200,
                {
                    "results": [
                        {
                            "title": "NPCI UPI Transaction Limit Rules",
                            "url": "https://www.npci.org.in/what-we-do/upi/product-overview",
                            "content": "Standard UPI daily cap is INR 1 lakh.",
                            "raw_content": "Full NPCI circular details on daily UPI limits.",
                            "published_date": "2026-01-10",
                        },
                        {
                            "title": "Internal Leak",
                            "url": "http://127.0.0.1:5432/leak",
                            "content": "Should be filtered out",
                        },
                    ]
                },
            )

    monkeypatch.setattr(httpx, "Client", _ClientOk)
    ok_res = TavilyProvider(api_key="tvly-test-key").search(req)
    assert ok_res.status == "completed"
    assert len(ok_res.sources) == 1
    assert ok_res.sources[0].domain == "www.npci.org.in"
    assert ok_res.sources[0].content_available is True

    # 3. 429 rate limit & timeout
    class _Client429(_ClientOk):
        def post(self, url, json=None, headers=None):
            return _MockResponse(429, {"detail": "Rate limit"})

    monkeypatch.setattr(httpx, "Client", _Client429)
    res_429 = TavilyProvider(api_key="tvly-test-key").search(req)
    assert res_429.status == "rate_limited"

    class _ClientTimeout(_ClientOk):
        def post(self, url, json=None, headers=None):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "Client", _ClientTimeout)
    res_timeout = TavilyProvider(api_key="tvly-test-key").search(req)
    assert res_timeout.status == "timeout"


def test_langsearch_provider_success_empty_and_malformed(monkeypatch):
    req = WebSearchRequest(query="Section 80C PPF ELSS India", max_results=3, include_content=True)

    assert LangSearchProvider(api_key="").search(req).status == "unconfigured"

    class _ClientLs:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            return _MockResponse(
                200,
                {
                    "code": 200,
                    "data": {
                        "webPages": {
                            "value": [
                                {
                                    "name": "Income Tax India Section 80C",
                                    "url": "https://incometaxindia.gov.in/80c",
                                    "snippet": "Deductions up to INR 1.5 lakh under old regime.",
                                    "text": "Detailed statutory text for Section 80C.",
                                    "datePublished": "2026-02-01",
                                }
                            ]
                        }
                    },
                },
            )

    monkeypatch.setattr(httpx, "Client", _ClientLs)
    ok_res = LangSearchProvider(api_key="ls-test").search(req)
    assert ok_res.status == "completed"
    assert len(ok_res.sources) == 1
    assert ok_res.sources[0].provider == "langsearch"

    class _ClientBadJson(_ClientLs):
        def post(self, url, json=None, headers=None):
            return _MockResponse(200, ValueError("bad json"))

    monkeypatch.setattr(httpx, "Client", _ClientBadJson)
    bad = LangSearchProvider(api_key="ls-test").search(req)
    assert bad.status == "error"

    class _Client401(_ClientLs):
        def post(self, url, json=None, headers=None):
            return _MockResponse(401, {})

    monkeypatch.setattr(httpx, "Client", _Client401)
    auth_err = LangSearchProvider(api_key="ls-bad").search(req)
    assert auth_err.status == "error"
    assert "credentials" in (auth_err.error_message or "").lower()


def test_firecrawl_provider_partial_scrape_and_no_silent_fallback(monkeypatch):
    req = WebSearchRequest(query="PPF interest rate 2026 India", max_results=3, include_content=True)

    # Firecrawl selective scrape: 1st succeeds, 2nd scrape fails -> search still returns partial result cleanly
    class _ClientFc:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None, headers=None):
            if url.endswith("/v2/search"):
                return _MockResponse(
                    200,
                    {
                        "success": True,
                        "data": {
                            "web": [
                                {
                                    "title": "RBI PPF Circular",
                                    "url": "https://www.rbi.org.in/ppf",
                                    "description": "PPF rate 7.1%",
                                },
                                {
                                    "title": "India Post Savings",
                                    "url": "https://www.indiapost.gov.in/ppf",
                                    "description": "Public Provident Fund scheme",
                                },
                            ]
                        },
                    },
                )
            if url.endswith("/v2/scrape"):
                target = (json or {}).get("url", "")
                if "rbi.org.in" in target:
                    return _MockResponse(
                        200,
                        {"success": True, "data": {"markdown": "Full scraped RBI markdown text."}},
                    )
                return _MockResponse(500, {"error": "Scrape failed"})
            raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(httpx, "Client", _ClientFc)
    res = FirecrawlProvider(api_key="fc-test").search(req)
    assert res.status == "completed"
    assert len(res.sources) == 2
    assert res.sources[0].content_available is True
    assert res.sources[1].snippet == "Public Provident Fund scheme"

    # CRITICAL: Selecting an unconfigured provider must NOT fall back to another configured provider
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-live-mock")
    monkeypatch.setattr(settings, "FIRECRAWL_API_KEY", "")
    fc_res = WebResearchService().execute_search(provider_id="firecrawl", query="PPF rate")
    assert fc_res.provider == "firecrawl"
    assert fc_res.status == "unconfigured"
    assert fc_res.sources == []


def test_personal_finance_rag_isolation_confirmation_and_cleanup(rag_api_client):
    tc, created_emails = rag_api_client
    _, user_a = _register_and_login(tc, created_emails, "rag_a")
    _, user_b = _register_and_login(tc, created_emails, "rag_b")

    with TestingSessionLocal() as db:
        doc_a_confirmed = FinancialDocument(
            user_id=user_a.id,
            original_filename="apollo_invoice.pdf",
            file_type="pdf",
            content_type="application/pdf",
            file_size=1024,
            file_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            storage_key=f"local/{uuid.uuid4().hex}.pdf",
            document_category="receipt",
            processing_status="confirmed",
            ocr_status="completed",
            page_count=2,
        )
        doc_a_unreviewed = FinancialDocument(
            user_id=user_a.id,
            original_filename="draft_lease.pdf",
            file_type="pdf",
            content_type="application/pdf",
            file_size=1024,
            file_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            storage_key=f"local/{uuid.uuid4().hex}.pdf",
            document_category="rent_agreement",
            processing_status="extracted",
            ocr_status="completed",
            page_count=1,
        )
        doc_b_secret = FinancialDocument(
            user_id=user_b.id,
            original_filename="user_b_salary_slip.pdf",
            file_type="pdf",
            content_type="application/pdf",
            file_size=1024,
            file_hash=uuid.uuid4().hex + uuid.uuid4().hex,
            storage_key=f"local/{uuid.uuid4().hex}.pdf",
            document_category="salary_slip",
            processing_status="confirmed",
            ocr_status="completed",
            page_count=1,
        )
        db.add_all([doc_a_confirmed, doc_a_unreviewed, doc_b_secret])
        db.flush()

        db.add_all(
            [
                DocumentExtraction(
                    document_id=doc_a_confirmed.id,
                    user_id=user_a.id,
                    ocr_engine="rapidocr",
                    merchant_name="Apollo Pharmacy",
                    invoice_number="INV-909",
                    invoice_date=dt.date(2026, 11, 10),
                    grand_total="1450.00",
                    raw_text="--- Page 1 ---\nApollo Pharmacy prescription bill\n--- Page 2 ---\nTotal INR 1450.00 paid via UPI",
                    field_confidence={},
                    processing_metadata={},
                ),
                DocumentExtraction(
                    document_id=doc_a_unreviewed.id,
                    user_id=user_a.id,
                    ocr_engine="rapidocr",
                    merchant_name="Whitefield Landlord",
                    grand_total="22000.00",
                    raw_text="Monthly rent agreement INR 22000",
                    field_confidence={},
                    processing_metadata={},
                ),
                DocumentExtraction(
                    document_id=doc_b_secret.id,
                    user_id=user_b.id,
                    ocr_engine="rapidocr",
                    merchant_name="Secret Corp India",
                    grand_total="999999.00",
                    raw_text="Confidential Secret Corp CTC 999999",
                    field_confidence={},
                    processing_metadata={},
                ),
            ]
        )
        db.commit()

        scanned, indexed, removed = reindex_user_documents(db, user_a.id)
        db.commit()
        assert scanned == 2
        assert indexed >= 2
        assert removed == 0

        # Idempotent reindex (deduplicated content_hash)
        _, indexed_again, _ = reindex_user_documents(db, user_a.id)
        db.commit()
        assert indexed_again == 0

        results_a, evidence_a = retrieve_personal_documents(
            db, user_a.id, "Apollo Pharmacy prescription rent Secret Corp"
        )
        db.commit()
        assert any("Apollo Pharmacy" in str(r) for r in results_a)
        assert not any("Secret Corp" in str(r) for r in results_a)

        confirmed_ev = [e for e in evidence_a if doc_a_confirmed.original_filename in e.title]
        unrev_ev = [e for e in evidence_a if doc_a_unreviewed.original_filename in e.title]
        assert confirmed_ev and all(e.is_confirmed_source is True for e in confirmed_ev)
        assert any(e.meta.get("page_number") in (1, 2) for e in confirmed_ev)
        if unrev_ev:
            assert all(e.is_confirmed_source is False for e in unrev_ev)

        # Rejecting doc_a_unreviewed purges its RAG chunks
        doc_a_unreviewed.processing_status = "rejected"
        db.add(doc_a_unreviewed)
        purged = purge_document_chunks(db, user_a.id, doc_a_unreviewed.id)
        db.commit()
        assert purged >= 1

        results_after, _ = retrieve_personal_documents(db, user_a.id, "Whitefield Landlord rent")
        assert not any("Whitefield Landlord" in str(r) for r in results_after)
