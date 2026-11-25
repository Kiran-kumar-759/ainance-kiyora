import datetime as dt
import uuid
from collections.abc import Generator
from decimal import Decimal
from unittest.mock import MagicMock

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
from app.services.ai.ai_provider import CategorizationAiInput
from app.services.ai.ai_validation import sanitize_text_for_ai, validate_groq_categorization
from app.services.ai.groq_provider import GroqAiProvider
from app.services.ai.merchant_intelligence import normalize_merchant_text
from tests.conftest import TestingSessionLocal


@pytest.fixture
def intel_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
                cleanup.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id))
                cleanup.execute(
                    delete(LedgerEntry).where(
                        LedgerEntry.journal_id.in_(
                            select(LedgerJournal.id).where(LedgerJournal.user_id == user.id)
                        )
                    )
                )
                cleanup.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
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


def _create_bank_account(tc: TestClient, headers: dict[str, str]) -> str:
    res = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "HDFC Savings",
            "account_type": "savings",
            "institution_name": "HDFC Bank",
            "currency": "INR",
            "opening_balance": "100000.00",
        },
        headers=headers,
    )
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def _post_tx(
    tc: TestClient,
    headers: dict[str, str],
    account_id: str,
    *,
    tx_type: str = "expense",
    amount: str = "450.00",
    description: str = "UPI/SWIGGY@ICICI/9823412",
    merchant_payee: str | None = None,
    category_id: str | None = None,
    tx_date: str | None = None,
) -> dict:
    payload = {
        "account_id": account_id,
        "transaction_type": tx_type,
        "amount": amount,
        "currency": "INR",
        "description": description,
        "merchant_payee": merchant_payee,
        "category_id": category_id,
        "transaction_date": tx_date or dt.date.today().isoformat(),
    }
    res = tc.post("/api/v1/finance/transactions", json=payload, headers=headers)
    assert res.status_code in (200, 201), res.text
    return res.json()


def test_merchant_normalization_and_ai_validation_unit():
    sw = normalize_merchant_text("UPI/SWIGGY@ICICI/123456789/ORDER998", None)
    assert sw.canonical_key == "swiggy"
    assert sw.normalized_name == "Swiggy"
    assert sw.known_default_category == "Food & Dining"

    bes = normalize_merchant_text("NEFT-BESCOM ELECTRICITY BILL-992211", None)
    assert bes.canonical_key == "bescom"
    assert bes.normalized_name == "BESCOM Electricity"

    sanitized = sanitize_text_for_ai("Paid to user@okaxis acct 12345678901234 phone 9876543210")
    assert "12345678901234" not in sanitized
    assert "9876543210" not in sanitized
    assert "user@okaxis" not in sanitized

    # Reject category not in allow-list
    assert validate_groq_categorization(
        '{"suggested_category": "Crypto Casino", "confidence": 0.9, "explanation": "Guess"}',
        ["Food & Dining", "Shopping"],
    ) is None

    valid = validate_groq_categorization(
        '{"suggested_category": "food & dining", "normalized_merchant": "Local Bakery", "confidence": 0.87, "explanation": "Matched bakery keyword."}',
        ["Food & Dining", "Shopping"],
    )
    assert valid is not None
    assert valid.suggested_category == "Food & Dining"


def test_groq_adapter_fallback_and_mocked_success(monkeypatch):
    disabled = GroqAiProvider(enabled=False, api_key="dummy")
    assert disabled.is_available() is False
    assert (
        disabled.categorize_transaction(
            CategorizationAiInput(
                transaction_type="expense",
                sanitized_description="Something obscure",
                sanitized_merchant="Obscure Co",
                amount_band="INR 200 - 1,000",
                allowed_categories=("Food & Dining", "Shopping"),
            )
        )
        is None
    )

    enabled = GroqAiProvider(enabled=True, api_key="test-key-never-logged")
    assert enabled.is_available() is True

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(
            message=MagicMock(
                content='{"suggested_category": "Healthcare", "normalized_merchant": "City Diagnostics", "confidence": 0.88, "explanation": "Lab diagnostic visit."}'
            )
        )
    ]
    mock_client.chat.completions.create.return_value = mock_resp
    monkeypatch.setattr(enabled, "_build_client", lambda: mock_client)

    parsed = enabled.categorize_transaction(
        CategorizationAiInput(
            transaction_type="expense",
            sanitized_description="POS CITY PATH LAB 4412",
            sanitized_merchant="City Path Lab",
            amount_band="INR 1,000 - 5,000",
            allowed_categories=("Food & Dining", "Healthcare", "Shopping"),
        )
    )
    assert parsed is not None
    assert parsed.suggested_category == "Healthcare"
    assert parsed.normalized_merchant == "City Diagnostics"

    # Exception in SDK must fall back cleanly to None
    mock_client.chat.completions.create.side_effect = RuntimeError("Network timeout")
    assert (
        enabled.categorize_transaction(
            CategorizationAiInput(
                transaction_type="expense",
                sanitized_description="POS CITY PATH LAB 4412",
                sanitized_merchant="City Path Lab",
                amount_band="INR 1,000 - 5,000",
                allowed_categories=("Healthcare",),
            )
        )
        is None
    )


def test_layered_categorization_override_feedback_and_ml_training(intel_client):
    tc, created_emails = intel_client
    # Require auth
    assert tc.get("/api/v1/intelligence/overview").status_code == 401

    headers = _register_and_login(tc, created_emails, "intel_cat")
    acc_id = _create_bank_account(tc, headers)

    cats = tc.get("/api/v1/finance/categories", headers=headers).json()
    cat_by_name = {c["name"]: c["id"] for c in cats}

    # Create uncategorized + pre-labeled transactions (< 12 labeled first)
    tx_swiggy = _post_tx(
        tc,
        headers,
        acc_id,
        description="UPI/SWIGGY@ICICI/12345678/ORD",
        amount="380.00",
        category_id=None,
    )
    tx_custom = _post_tx(
        tc,
        headers,
        acc_id,
        description="UPI/RAMESH KIRANA STORE/551234",
        amount="620.00",
        category_id=None,
    )

    # CSRF check
    bad_csrf = tc.post("/api/v1/intelligence/run", json={"reanalyze_all": False})
    assert bad_csrf.status_code == 403

    # Run full pipeline (Groq disabled by default -> local deterministic + insufficient data ML)
    run_res = tc.post(
        "/api/v1/intelligence/run",
        json={"reanalyze_all": False, "use_ai_fallback": True, "train_model": True},
        headers=headers,
    )
    assert run_res.status_code == 200, run_res.text
    job = run_res.json()
    assert job["status"] == "completed"
    assert job["summary"]["ml_status"] == "insufficient_data"

    # Check Swiggy suggestion & explanation
    cats_list = tc.get("/api/v1/intelligence/categorizations", headers=headers).json()
    sw_rec = next(i for i in cats_list["items"] if i["transaction_id"] == tx_swiggy["id"])
    assert sw_rec["suggested_category_name"] == "Food & Dining"
    assert sw_rec["normalized_merchant_name"] == "Swiggy"
    assert sw_rec["classification_method"] == "deterministic_rule"
    assert sw_rec["review_status"] == "needs_review"

    # User overrides unknown kirana store -> Groceries & persists merchant mapping
    ov_res = tc.post(
        f"/api/v1/intelligence/categorizations/{tx_custom['id']}/override",
        json={
            "category_id": cat_by_name["Groceries"],
            "normalized_merchant_name": "Ramesh Kirana",
            "save_merchant_mapping": True,
            "action": "override",
            "notes": "Neighborhood grocery store",
        },
        headers=headers,
    )
    assert ov_res.status_code == 200, ov_res.text
    ov_data = ov_res.json()
    assert ov_data["review_status"] == "overridden"
    assert ov_data["current_category_id"] == cat_by_name["Groceries"]
    assert ov_data["normalized_merchant_name"] == "Ramesh Kirana"

    # Feedback audit log recorded
    fb = tc.get("/api/v1/intelligence/feedback", headers=headers).json()
    assert len(fb) == 1
    assert fb[0]["new_category_name"] == "Groceries"

    # New transaction matching same merchant should auto-apply confirmed mapping
    tx_custom_2 = _post_tx(
        tc,
        headers,
        acc_id,
        description="UPI/RAMESH KIRANA STORE/551234",
        amount="410.00",
        category_id=None,
    )
    tc.post("/api/v1/intelligence/categorize", json={}, headers=headers)
    cats_list_2 = tc.get("/api/v1/intelligence/categorizations", headers=headers).json()
    second_rec = next(i for i in cats_list_2["items"] if i["transaction_id"] == tx_custom_2["id"])
    assert second_rec["classification_method"] == "confirmed_mapping"
    assert second_rec["suggested_category_name"] == "Groceries"

    # Seed enough labeled data across 2 categories to train per-user TF-IDF classifier
    for idx in range(7):
        _post_tx(
            tc,
            headers,
            acc_id,
            description=f"Zomato lunch order #{idx} biryani",
            amount="320.00",
            category_id=cat_by_name["Food & Dining"],
        )
        _post_tx(
            tc,
            headers,
            acc_id,
            description=f"Uber auto ride #{idx} office commute",
            amount="190.00",
            category_id=cat_by_name["Transportation"],
        )

    ml_res = tc.post("/api/v1/intelligence/ml/train", json={}, headers=headers)
    assert ml_res.status_code == 200, ml_res.text
    ml_data = ml_res.json()
    assert ml_data["status"] == "trained"
    assert ml_data["training_sample_count"] >= 14
    assert ml_data["class_count"] >= 2
    assert Decimal(str(ml_data["accuracy"])) >= Decimal("0.50")

    # Cross-user isolation check: User B must not see User A's transactions, merchants, or ML model
    headers_b = _register_and_login(tc, created_emails, "intel_user_b")
    assert tc.get("/api/v1/intelligence/merchants", headers=headers_b).json()["total"] == 0
    assert tc.get("/api/v1/intelligence/ml/status", headers=headers_b).json() is None
    cross_ov = tc.post(
        f"/api/v1/intelligence/categorizations/{tx_custom['id']}/override",
        json={"category_id": cat_by_name["Shopping"], "action": "override"},
        headers=headers_b,
    )
    assert cross_ov.status_code == 404
