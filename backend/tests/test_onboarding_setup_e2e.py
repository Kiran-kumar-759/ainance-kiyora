import io
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.assistant import DocumentRagChunk
from app.models.documents import (
    DocumentExtraction,
    DocumentProcessingJob,
    FinancialDocument,
)
from app.models.finance import (
    BankingConnection,
    BankingSyncRun,
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.forecasting import FinancialForecast
from app.models.imports import ImportBatch, ImportMappingProfile, ImportRow
from app.models.intelligence import AiProcessingJob, MerchantIdentity, TransactionCategorization
from app.models.onboarding import UserOnboardingState
from app.models.user import User
from app.services.documents.doc_storage import PrivateDocumentStorage
from app.services.imports.storage import LocalPrivateFileStorage
from tests.conftest import TestingSessionLocal


def _cleanup_users(emails: list[str]) -> None:
    if not emails:
        return
    import_storage = LocalPrivateFileStorage()
    doc_storage = PrivateDocumentStorage()
    with TestingSessionLocal() as db:
        users = db.execute(select(User).where(User.email.in_(emails))).scalars().all()
        uids = [u.id for u in users]
        if not uids:
            return
        for uid in uids:
            shutil.rmtree(import_storage.base_dir / str(uid), ignore_errors=True)
            shutil.rmtree(doc_storage.base_dir / str(uid), ignore_errors=True)

        db.execute(delete(DocumentRagChunk).where(DocumentRagChunk.user_id.in_(uids)))
        db.execute(delete(DocumentExtraction).where(DocumentExtraction.user_id.in_(uids)))
        db.execute(delete(DocumentProcessingJob).where(DocumentProcessingJob.user_id.in_(uids)))
        db.execute(delete(FinancialDocument).where(FinancialDocument.user_id.in_(uids)))
        db.execute(delete(TransactionCategorization).where(TransactionCategorization.user_id.in_(uids)))
        db.execute(delete(MerchantIdentity).where(MerchantIdentity.user_id.in_(uids)))
        db.execute(delete(AiProcessingJob).where(AiProcessingJob.user_id.in_(uids)))
        db.execute(delete(FinancialForecast).where(FinancialForecast.user_id.in_(uids)))
        db.execute(
            delete(LedgerEntry).where(
                LedgerEntry.journal_id.in_(
                    select(LedgerJournal.id).where(LedgerJournal.user_id.in_(uids))
                )
            )
        )
        db.execute(delete(LedgerJournal).where(LedgerJournal.user_id.in_(uids)))
        db.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id.in_(uids)))
        db.execute(delete(FinancialTransfer).where(FinancialTransfer.user_id.in_(uids)))
        db.execute(
            delete(ImportRow).where(
                ImportRow.import_batch_id.in_(
                    select(ImportBatch.id).where(ImportBatch.user_id.in_(uids))
                )
            )
        )
        db.execute(delete(ImportBatch).where(ImportBatch.user_id.in_(uids)))
        db.execute(delete(ImportMappingProfile).where(ImportMappingProfile.user_id.in_(uids)))
        db.execute(delete(BankingSyncRun).where(BankingSyncRun.user_id.in_(uids)))
        db.execute(delete(BankingConnection).where(BankingConnection.user_id.in_(uids)))
        db.execute(delete(FinancialAccount).where(FinancialAccount.user_id.in_(uids)))
        db.execute(delete(FinancialCategory).where(FinancialCategory.user_id.in_(uids)))
        db.execute(delete(UserOnboardingState).where(UserOnboardingState.user_id.in_(uids)))
        db.execute(delete(User).where(User.id.in_(uids)))
        db.commit()


@pytest.fixture
def live_pg_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
    _cleanup_users(created_emails)


def _register_and_login(tc: TestClient, created_emails: list[str], tag: str) -> tuple[str, dict]:
    rate_limiter.clear()
    email = f"onb.{tag}.{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    reg = tc.post(
        "/api/v1/auth/register",
        json={"full_name": f"{tag} User", "email": email, "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201, reg.text
    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200, login.text
    csrf_token = login.cookies.get(settings.CSRF_COOKIE_NAME)
    if not csrf_token:
        csrf_token = tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return csrf_token, login.json()["user"]


def test_scenario_1_demo_bank_catalog_lifecycle_and_dashboard_gate(
    live_pg_client: tuple[TestClient, list[str]],
):
    """
    Scenario 1 & Catalog tests:
    Register -> Login -> Gate check (403) -> Profile -> Bank catalog & search ->
    Unsupported live bank rejection (503) -> Demo bank consent flow ->
    Discover accounts -> Selective import & initial sync -> Initialize workspace ->
    Dashboard allowed (200) -> Returning login skips onboarding -> Disconnect & Revoke.
    """
    tc, created_emails = live_pg_client
    csrf, user = _register_and_login(tc, created_emails, "demo")
    assert user["onboarding_completed"] is False

    # 1. Incomplete onboarding status & dashboard gate blocked when enforced
    status_res = tc.get("/api/v1/onboarding/status")
    assert status_res.status_code == 200
    st = status_res.json()
    assert st["onboarding_completed"] is False
    assert st["dashboard_access_allowed"] is False
    assert st["required_gate_view"] == "onboarding"
    assert st["current_stage"] == "registered"
    assert st["next_action"] == "complete_profile"

    assert tc.get("/api/v1/onboarding/dashboard-access").status_code == 403
    assert tc.get("/api/v1/finance/dashboard?enforce_onboarding=true").status_code == 403
    assert tc.get("/api/v1/analytics/dashboard?enforce_onboarding=true").status_code == 403

    # 2. Save Profile & Indian regional defaults
    prof_res = tc.post(
        "/api/v1/onboarding/profile",
        json={
            "first_name": "Aarav",
            "last_name": "Mehta",
            "phone_number": "+91 9876543210",
            "preferred_currency": "INR",
            "locale": "en-IN",
            "timezone": "Asia/Kolkata",
            "date_format": "DD/MM/YYYY",
            "monthly_budget": "45000.00",
            "monthly_income_range": "100000-150000",
            "financial_goals": ["Emergency Fund", "SIP"],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert prof_res.status_code == 200, prof_res.text
    prof = prof_res.json()
    assert prof["profile_completed"] is True
    assert prof["current_stage"] == "financial_data_setup"
    assert prof["profile"]["country"] == "India"
    assert prof["profile"]["financial_year"] == "April-March"
    assert prof["next_action"] == "choose_financial_setup"

    # 3. Bank institution catalog & search
    cat_res = tc.get("/api/v1/banking/institutions")
    assert cat_res.status_code == 200
    catalog = cat_res.json()
    assert catalog["live_aa_configured"] is False
    assert catalog["demo_available"] is True
    assert catalog["total"] >= 15

    search_res = tc.get("/api/v1/banking/institutions?search=hdfc")
    assert search_res.status_code == 200
    hdfc = search_res.json()["institutions"][0]
    assert hdfc["bank_id"] == "hdfc_bank"
    assert hdfc["is_demo"] is False
    assert hdfc["live_supported"] is False
    assert hdfc["connection_availability_status"] == "live_unavailable"
    assert hdfc["logo_url"] == "/assets/banks/hdfc.svg"

    # Unsupported real bank initiation returns clear 503 unavailable status
    unavail = tc.post(
        "/api/v1/banking/connections/initiate",
        json={"bank_id": "hdfc_bank", "connection_method": "account_aggregator", "consent_given": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert unavail.status_code == 503
    assert "not configured" in unavail.json()["detail"].lower()

    # 4. Select bank_connect & initiate demo connection awaiting consent
    sel_res = tc.post(
        "/api/v1/onboarding/financial-setup/select",
        json={"setup_method": "bank_connect", "bank_id": "demo_national_bank"},
        headers={"X-CSRF-Token": csrf},
    )
    assert sel_res.status_code == 200
    assert sel_res.json()["selected_setup_method"] == "bank_connect"

    init_conn = tc.post(
        "/api/v1/banking/connections/initiate",
        json={"bank_id": "demo_national_bank", "connection_method": "demo", "consent_given": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert init_conn.status_code == 200
    conn_data = init_conn.json()
    assert conn_data["lifecycle_state"] == "awaiting_consent"
    assert conn_data["status"] == "pending"
    assert conn_data["is_simulated"] is True
    conn_id = conn_data["id"]

    # Declined consent marks connection failed cleanly
    declined = tc.post(
        f"/api/v1/banking/connections/{conn_id}/consent",
        json={"consent_given": False},
        headers={"X-CSRF-Token": csrf},
    )
    assert declined.status_code == 200
    assert declined.json()["lifecycle_state"] == "failed"

    # Re-initiate and grant consent
    tc.post(
        "/api/v1/banking/connections/initiate",
        json={"bank_id": "demo_national_bank", "connection_method": "demo", "consent_given": False},
        headers={"X-CSRF-Token": csrf},
    )
    consented = tc.post(
        f"/api/v1/banking/connections/{conn_id}/consent",
        json={"consent_given": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert consented.status_code == 200
    assert consented.json()["lifecycle_state"] == "accounts_discovered"
    assert consented.json()["status"] == "connected"

    # Discover accounts updates lifecycle_state -> awaiting_account_selection
    disc = tc.get(f"/api/v1/banking/connections/{conn_id}/accounts")
    assert disc.status_code == 200
    assert len(disc.json()) == 2
    conn_detail = tc.get(f"/api/v1/banking/connections/{conn_id}").json()
    assert conn_detail["lifecycle_state"] == "awaiting_account_selection"

    # Import selected account with initial sync
    imp = tc.post(
        f"/api/v1/banking/connections/{conn_id}/accounts/import",
        json={"account_ids": ["dnb_sav_001"], "trigger_initial_sync": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert imp.status_code == 200
    assert len(imp.json()) == 1
    assert imp.json()[0]["source"] == "demo_bank"

    # 5. Run workspace initialization
    init_res = tc.post("/api/v1/onboarding/initialize", headers={"X-CSRF-Token": csrf})
    assert init_res.status_code == 200, init_res.text
    init_payload = init_res.json()
    assert init_payload["initialization_status"] == "completed"
    assert init_payload["onboarding_completed"] is True
    assert init_payload["dashboard_access_allowed"] is True
    assert len(init_payload["steps"]) == 6
    assert init_payload["summary"]["accounts_verified"] == 1
    assert init_payload["summary"]["transactions_count"] == 4

    # Dashboard gate now allowed
    assert tc.get("/api/v1/onboarding/dashboard-access").status_code == 200
    assert tc.get("/api/v1/finance/dashboard?enforce_onboarding=true").status_code == 200
    assert tc.get("/api/v1/analytics/dashboard?enforce_onboarding=true").status_code == 200

    # 6. Scenario 5: Returning user logs in again -> completed onboarding not repeated
    relogin = tc.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "StrongPassword123!"},
    )
    assert relogin.status_code == 200
    assert relogin.json()["user"]["onboarding_completed"] is True
    recheck = tc.get("/api/v1/onboarding/status").json()
    assert recheck["required_gate_view"] == "dashboard"
    assert recheck["next_action"] == "go_to_dashboard"

    # Revoke connection & verify feed deactivated cleanly
    rev_csrf = relogin.cookies.get(settings.CSRF_COOKIE_NAME)
    rev = tc.post(
        f"/api/v1/banking/connections/{conn_id}/revoke",
        headers={"X-CSRF-Token": rev_csrf},
    )
    assert rev.status_code == 200
    assert rev.json()["status"] == "revoked"
    assert rev.json()["lifecycle_state"] == "revoked"


def test_scenario_2_and_3_manual_account_and_statement_import_and_documents(
    live_pg_client: tuple[TestClient, list[str]],
):
    """
    Scenario 2 & 3 & Document upload tests:
    Manual account creation + CSV statement import + document upload -> initialize ->
    verify real accounts, transactions, deterministic categorization, and document RAG.
    """
    tc, created_emails = live_pg_client
    csrf, _ = _register_and_login(tc, created_emails, "manualimport")

    tc.post(
        "/api/v1/onboarding/profile",
        json={"first_name": "Neha", "last_name": "Kulkarni"},
        headers={"X-CSRF-Token": csrf},
    )
    tc.post(
        "/api/v1/onboarding/financial-setup/select",
        json={"setup_method": "manual_account"},
        headers={"X-CSRF-Token": csrf},
    )

    acc_res = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "HDFC Primary Savings",
            "account_type": "savings",
            "institution_name": "HDFC Bank",
            "opening_balance": "50000.00",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert acc_res.status_code == 200, acc_res.text
    account_id = acc_res.json()["id"]
    assert acc_res.json()["source"] == "manual"

    # Upload CSV statement and commit via Phase 3 import pipeline
    csv_bytes = (
        b"Date,Description,Withdrawal Amt,Deposit Amt\n"
        b"2026-11-01,Salary Credit Acme Pvt Ltd,,90000.00\n"
        b"2026-11-03,Swiggy Food Order,450.00,\n"
        b"2026-11-05,BigBasket Groceries,1200.00,\n"
        b"2026-11-10,BESCOM Electricity Bill,1800.00,\n"
    )
    up = tc.post(
        "/api/v1/imports/upload",
        data={"account_id": account_id},
        files={"file": ("statement.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers={"X-CSRF-Token": csrf},
    )
    assert up.status_code == 201, up.text
    batch_id = up.json()["batch"]["id"]

    # Map & validate & commit
    map_res = tc.put(
        f"/api/v1/imports/{batch_id}/mapping",
        json={
            "date_column": "Date",
            "description_column": "Description",
            "amount_mode": "split",
            "debit_column": "Withdrawal Amt",
            "credit_column": "Deposit Amt",
            "date_format": "YYYY-MM-DD",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert map_res.status_code == 200, map_res.text
    val_res = tc.post(f"/api/v1/imports/{batch_id}/validate", headers={"X-CSRF-Token": csrf})
    assert val_res.status_code == 200
    commit_res = tc.post(f"/api/v1/imports/{batch_id}/commit", headers={"X-CSRF-Token": csrf})
    assert commit_res.status_code == 200
    assert commit_res.json()["imported_count"] == 4

    # Upload a valid PNG receipt document cleanly without OCR crashing test suite
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(buf, format="PNG")
    doc_up = tc.post(
        "/api/v1/documents/upload",
        data={"document_category": "electricity_bill", "auto_process": "false"},
        files={"file": ("bescom_bill.png", io.BytesIO(buf.getvalue()), "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    assert doc_up.status_code == 201, doc_up.text

    # Initialize workspace
    init_res = tc.post("/api/v1/onboarding/initialize", headers={"X-CSRF-Token": csrf})
    assert init_res.status_code == 200, init_res.text
    summary = init_res.json()["summary"]
    assert summary["accounts_verified"] == 1
    assert summary["transactions_count"] == 4
    assert summary["categorized_count"] == 4
    assert summary["documents_count"] == 1

    # Balance is exact Decimal: 50000 + 90000 - (450 + 1200 + 1800) = 136550.00
    acc_after = tc.get(f"/api/v1/finance/accounts/{account_id}").json()
    assert Decimal(str(acc_after["current_balance"])) == Decimal("136550.00")


def test_scenario_4_skip_setup_and_failure_retry_and_duplicate_guard(
    live_pg_client: tuple[TestClient, list[str]],
):
    """
    Scenario 4 + Duplicate guard + Failure & Retry:
    Register -> Login -> Profile -> Skip financial setup -> Failed initialization persisted ->
    Retry succeeds cleanly -> Zero fake financial data created -> 409 on duplicate in_progress init.
    """
    tc, created_emails = live_pg_client
    csrf, _ = _register_and_login(tc, created_emails, "skipretry")

    tc.post(
        "/api/v1/onboarding/profile",
        json={"first_name": "Rohan", "last_name": "Verma"},
        headers={"X-CSRF-Token": csrf},
    )

    skip_res = tc.post(
        "/api/v1/onboarding/financial-setup/skip",
        json={"complete_onboarding": False, "reason": "Will connect accounts later"},
        headers={"X-CSRF-Token": csrf},
    )
    assert skip_res.status_code == 200
    sk = skip_res.json()
    assert sk["financial_setup_skipped"] is True
    assert sk["financial_setup_status"] == "skipped"
    assert sk["accounts_count"] == 0
    assert sk["transactions_count"] == 0
    assert sk["has_active_banking_connection"] is False

    # Simulate step failure during initialization & confirm clean retry recovery
    with patch(
        "app.services.workspace_init_service.WorkspaceInitializationService._step_preparing_insights",
        side_effect=RuntimeError("Simulated transient analytics error"),
    ):
        fail_res = tc.post("/api/v1/onboarding/initialize", headers={"X-CSRF-Token": csrf})
        assert fail_res.status_code == 500

    init_st = tc.get("/api/v1/onboarding/initialization-status").json()
    assert init_st["initialization_status"] == "failed"
    assert "Simulated transient analytics error" in (init_st["initialization_error"] or "")
    assert init_st["dashboard_access_allowed"] is False

    # Verify duplicate in_progress lock returns 409 Conflict cleanly
    with TestingSessionLocal() as db:
        u = db.execute(select(User).where(User.email == created_emails[0])).scalar_one()
        st_row = db.execute(
            select(UserOnboardingState).where(UserOnboardingState.user_id == u.id)
        ).scalar_one()
        st_row.initialization_status = "in_progress"
        db.commit()

    dup_res = tc.post("/api/v1/onboarding/initialize", headers={"X-CSRF-Token": csrf})
    assert dup_res.status_code == 409

    with TestingSessionLocal() as db:
        u = db.execute(select(User).where(User.email == created_emails[0])).scalar_one()
        st_row = db.execute(
            select(UserOnboardingState).where(UserOnboardingState.user_id == u.id)
        ).scalar_one()
        st_row.initialization_status = "failed"
        db.commit()

    # Retry succeeds and completes onboarding with zero fake data
    retry_res = tc.post("/api/v1/onboarding/initialize/retry", headers={"X-CSRF-Token": csrf})
    assert retry_res.status_code == 200, retry_res.text
    retry_data = retry_res.json()
    assert retry_data["initialization_status"] == "completed"
    assert retry_data["onboarding_completed"] is True
    assert retry_data["dashboard_access_allowed"] is True
    assert retry_data["summary"]["accounts_verified"] == 0
    assert retry_data["summary"]["transactions_count"] == 0

    final_status = tc.get("/api/v1/onboarding/status").json()
    assert final_status["financial_setup_skipped"] is True
    assert final_status["has_active_banking_connection"] is False
    assert final_status["accounts_count"] == 0
    assert "require" in final_status["guidance_message"].lower() or "once you connect" in final_status["guidance_message"].lower()


def test_scenario_6_cross_tenant_isolation_and_csrf_enforcement(
    live_pg_client: tuple[TestClient, list[str]],
):
    """
    Scenario 6: Verify strict multi-user isolation across onboarding, connections, accounts,
    and CSRF requirement on onboarding/banking mutations.
    """
    tc, created_emails = live_pg_client
    csrf_a, _ = _register_and_login(tc, created_emails, "tenantA")
    # Missing CSRF rejected
    no_csrf = tc.post("/api/v1/onboarding/profile", json={"first_name": "X"})
    assert no_csrf.status_code == 403

    # User A creates demo connection & manual account
    conn_a = tc.post(
        "/api/v1/banking/connections/initiate",
        json={"bank_id": "demo_private_bank", "connection_method": "demo", "consent_given": True},
        headers={"X-CSRF-Token": csrf_a},
    ).json()
    acc_a = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "Tenant A Cash", "account_type": "cash", "opening_balance": "1000.00"},
        headers={"X-CSRF-Token": csrf_a},
    ).json()

    # Switch to User B
    csrf_b, _ = _register_and_login(tc, created_emails, "tenantB")
    assert tc.get(f"/api/v1/banking/connections/{conn_a['id']}").status_code == 404
    assert tc.post(
        f"/api/v1/banking/connections/{conn_a['id']}/sync",
        headers={"X-CSRF-Token": csrf_b},
    ).status_code == 404
    assert tc.get(f"/api/v1/finance/accounts/{acc_a['id']}").status_code == 404
    assert tc.get("/api/v1/onboarding/status").json()["accounts_count"] == 0
