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
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.intelligence import (
    AiModelMetadata,
    AiProcessingJob,
    CategorizationFeedback,
    FinancialInsight,
    MerchantAlias,
    MerchantCategoryMapping,
    MerchantIdentity,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)
from app.models.subscriptions import Subscription
from app.models.user import User
from app.services.ai.worker import ai_intelligence_worker
from tests.conftest import TestingSessionLocal


@pytest.fixture
def intel_analytics_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
    cleanup = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                cleanup.execute(delete(CategorizationFeedback).where(CategorizationFeedback.user_id == user.id))
                cleanup.execute(delete(TransactionCategorization).where(TransactionCategorization.user_id == user.id))
                cleanup.execute(delete(MerchantCategoryMapping).where(MerchantCategoryMapping.user_id == user.id))
                cleanup.execute(delete(MerchantAlias).where(MerchantAlias.user_id == user.id))
                cleanup.execute(delete(RecurringPaymentCandidate).where(RecurringPaymentCandidate.user_id == user.id))
                cleanup.execute(delete(MerchantIdentity).where(MerchantIdentity.user_id == user.id))
                cleanup.execute(delete(SpendingAnomaly).where(SpendingAnomaly.user_id == user.id))
                cleanup.execute(delete(FinancialInsight).where(FinancialInsight.user_id == user.id))
                cleanup.execute(delete(AiModelMetadata).where(AiModelMetadata.user_id == user.id))
                cleanup.execute(delete(AiProcessingJob).where(AiProcessingJob.user_id == user.id))
                cleanup.execute(delete(Subscription).where(Subscription.user_id == user.id))
                cleanup.execute(
                    delete(LedgerEntry).where(
                        LedgerEntry.journal_id.in_(
                            select(LedgerJournal.id).where(LedgerJournal.user_id == user.id)
                        )
                    )
                )
                cleanup.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
                cleanup.execute(delete(FinancialTransfer).where(FinancialTransfer.user_id == user.id))
                cleanup.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id))
                cleanup.execute(delete(FinancialAccount).where(FinancialAccount.user_id == user.id))
                cleanup.execute(delete(FinancialCategory).where(FinancialCategory.user_id == user.id))
                cleanup.execute(delete(User).where(User.id == user.id))
        cleanup.commit()
    finally:
        cleanup.close()


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> dict[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    pw = "StrongPass#2026"
    r1 = tc.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": pw,
            "full_name": f"Test {prefix}",
            "mobile_number": "+919876543210",
        },
    )
    assert r1.status_code in (200, 201), r1.text
    r2 = tc.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200, r2.text
    csrf = r2.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def _create_accounts(tc: TestClient, headers: dict[str, str]) -> tuple[str, str]:
    r1 = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "ICICI Savings",
            "account_type": "savings",
            "currency": "INR",
            "opening_balance": "250000.00",
        },
        headers=headers,
    )
    r2 = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Axis Savings",
            "account_type": "savings",
            "currency": "INR",
            "opening_balance": "20000.00",
        },
        headers=headers,
    )
    return r1.json()["id"], r2.json()["id"]


def test_recurring_patterns_anomalies_insights_and_worker(intel_analytics_client):
    tc, created_emails = intel_analytics_client
    headers = _register_and_login(tc, created_emails, "intel_an")
    acc1, acc2 = _create_accounts(tc, headers)

    cats = tc.get("/api/v1/finance/categories", headers=headers).json()
    cat_by_name = {c["name"]: c["id"] for c in cats}

    today = dt.date.today()

    def _add(tx_type, amount, desc, cat_name, days_ago, acc=acc1):
        d = (today - dt.timedelta(days=days_ago)).isoformat()
        res = tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc,
                "transaction_type": tx_type,
                "amount": amount,
                "currency": "INR",
                "description": desc,
                "category_id": cat_by_name.get(cat_name),
                "transaction_date": d,
            },
            headers=headers,
        )
        assert res.status_code in (200, 201), res.text
        return res.json()

    # Fixed monthly subscription (Netflix 499 x 3 months) + variable electricity (BESCOM)
    _add("expense", "499.00", "ACH/NETFLIX INDIA", "Subscriptions", 70)
    _add("expense", "499.00", "ACH/NETFLIX INDIA", "Subscriptions", 40)
    _add("expense", "499.00", "ACH/NETFLIX INDIA", "Subscriptions", 10)

    _add("expense", "1450.00", "UPI/BESCOM ELECTRICITY", "Utilities & Bills", 72)
    _add("expense", "1780.00", "UPI/BESCOM ELECTRICITY", "Utilities & Bills", 42)
    _add("expense", "2420.00", "UPI/BESCOM ELECTRICITY", "Utilities & Bills", 12)  # also price jump

    # Food & Dining baseline + statistical spike
    for d_ago in (60, 50, 38, 25, 18):
        _add("expense", "350.00", "UPI/SWIGGY@ICICI", "Food & Dining", d_ago)
    _add("expense", "5500.00", "POS FINE DINING PARTY", "Food & Dining", 4)

    # Salary income
    _add("income", "85000.00", "NEFT ACME SALARY CR", "Salary", 15)

    # Transfer between own accounts MUST be excluded from spending totals
    tr = tc.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": acc1,
            "destination_account_id": acc2,
            "amount": "15000.00",
            "transfer_date": today.isoformat(),
            "description": "Self transfer",
        },
        headers=headers,
    )
    assert tr.status_code in (200, 201), tr.text

    # Enqueue async job and run PostgreSQL worker directly
    q_res = tc.post(
        "/api/v1/intelligence/run",
        json={"async_job": True, "lookback_days": 180},
        headers=headers,
    )
    assert q_res.status_code == 200, q_res.text
    assert q_res.json()["status"] == "queued"

    processed = ai_intelligence_worker.process_pending_batch(max_jobs=2)
    assert processed == 1

    # 1. Verify Recurring Detection (Netflix + variable BESCOM)
    recur = tc.get("/api/v1/intelligence/recurring-candidates", headers=headers).json()
    keys = {item["merchant_key"]: item for item in recur["items"]}
    assert "netflix" in keys
    assert keys["netflix"]["frequency"] == "monthly"
    assert Decimal(str(keys["netflix"]["estimated_amount"])) == Decimal("499.00")
    assert "bescom" in keys
    assert keys["bescom"]["is_variable_amount"] is True

    # Confirm Netflix & create real Phase 6 Subscription
    dec_res = tc.post(
        f"/api/v1/intelligence/recurring-candidates/{keys['netflix']['id']}/decision",
        json={"decision": "confirm", "create_subscription": True},
        headers=headers,
    )
    assert dec_res.status_code == 200, dec_res.text
    assert dec_res.json()["review_status"] == "linked"
    assert dec_res.json()["linked_subscription_id"] is not None

    subs_resp = tc.get("/api/v1/subscriptions", headers=headers).json()
    subs = subs_resp["items"] if isinstance(subs_resp, dict) else subs_resp
    assert any(s["id"] == dec_res.json()["linked_subscription_id"] for s in subs)

    # 2. Verify Spending Patterns exclude transfer (15,000) and sum real expenses accurately
    pat = tc.get("/api/v1/intelligence/patterns", headers=headers).json()
    expected_expense = Decimal("499") * 3 + Decimal("1450") + Decimal("1780") + Decimal("2420") + Decimal("350") * 5 + Decimal("5500")
    assert Decimal(str(pat["total_expense"])) == expected_expense
    assert Decimal(str(pat["total_income"])) == Decimal("85000.00")

    # 3. Verify Statistical Anomalies detected cleanly (never mentions 'fraud')
    anoms = tc.get("/api/v1/intelligence/anomalies", headers=headers).json()
    assert anoms["total"] >= 1
    for a in anoms["items"]:
        assert "fraud" not in a["explanation"].lower()

    first_anom_id = anoms["items"][0]["id"]
    ack_res = tc.post(
        f"/api/v1/intelligence/anomalies/{first_anom_id}/review",
        json={"action": "acknowledge"},
        headers=headers,
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["review_status"] == "acknowledged"

    # 4. Verify Insights generated and read/dismiss workflow works
    ins = tc.get("/api/v1/intelligence/insights", headers=headers).json()
    assert ins["total"] >= 1
    first_ins_id = ins["items"][0]["id"]
    read_res = tc.post(
        f"/api/v1/intelligence/insights/{first_ins_id}/review",
        json={"action": "mark_read"},
        headers=headers,
    )
    assert read_res.status_code == 200
    assert read_res.json()["status"] == "read"
