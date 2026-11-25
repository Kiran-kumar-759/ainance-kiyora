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
from app.models.bills import Bill, BillRecurrenceSchedule
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.forecasting import (
    FinancialForecast,
    ForecastEvaluation,
    ForecastExplanation,
    ForecastScenario,
    ForecastValue,
)
from app.models.intelligence import AiProcessingJob, RecurringPaymentCandidate
from app.models.loans import Loan, LoanInstallment
from app.models.subscriptions import Subscription
from app.models.user import User
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.schemas.forecasting import GenerateForecastRequest
from app.services.forecasting.forecast_service import ForecastService
from tests.conftest import TestingSessionLocal


@pytest.fixture
def fc_client() -> Generator[tuple[TestClient, list[str]], None, None]:
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
                cleanup.execute(delete(ForecastExplanation).where(ForecastExplanation.user_id == user.id))
                cleanup.execute(delete(ForecastValue).where(ForecastValue.user_id == user.id))
                cleanup.execute(delete(FinancialForecast).where(FinancialForecast.user_id == user.id))
                cleanup.execute(delete(ForecastScenario).where(ForecastScenario.user_id == user.id))
                cleanup.execute(delete(ForecastEvaluation).where(ForecastEvaluation.user_id == user.id))
                cleanup.execute(delete(AiProcessingJob).where(AiProcessingJob.user_id == user.id))
                cleanup.execute(delete(RecurringPaymentCandidate).where(RecurringPaymentCandidate.user_id == user.id))
                cleanup.execute(delete(LoanInstallment).where(LoanInstallment.user_id == user.id))
                cleanup.execute(delete(Loan).where(Loan.user_id == user.id))
                cleanup.execute(delete(Subscription).where(Subscription.user_id == user.id))
                cleanup.execute(delete(Bill).where(Bill.user_id == user.id))
                cleanup.execute(
                    delete(BillRecurrenceSchedule).where(BillRecurrenceSchedule.user_id == user.id)
                )
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


def test_insufficient_data_and_unknown_variable_bills(fc_client):
    tc, created_emails = fc_client
    headers = _register_and_login(tc, created_emails, "fc_insuf")

    # Empty user -> explicit insufficient_data, never fabricated numbers
    ov = tc.get("/api/v1/forecasting/overview?horizon_days=30", headers=headers)
    assert ov.status_code == 200, ov.text
    data = ov.json()
    assert data["forecast"]["status"] == "insufficient_data"
    assert data["forecast"]["confidence_label"] == "insufficient_data"
    assert data["expenses"]["predicted_total"] is None
    assert data["income"]["predicted_total"] is None

    # Create bank account + variable unknown bill + unconfirmed Phase 8 candidate
    acc = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "SBI Checking", "account_type": "savings", "opening_balance": "40000.00"},
        headers=headers,
    ).json()

    tomorrow = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    b_res = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "BESCOM Meter Variable",
            "bill_category": "electricity",
            "bill_type": "one_time",
            "is_variable_amount": True,
            "due_date": tomorrow,
            "linked_account_id": acc["id"],
        },
        headers=headers,
    )
    assert b_res.status_code in (200, 201), b_res.text

    # Add unconfirmed Phase 8 candidate in DB
    db = TestingSessionLocal()
    try:
        user_id = uuid.UUID(acc["user_id"])
        db.add(
            RecurringPaymentCandidate(
                user_id=user_id,
                merchant_key="gym_cand",
                merchant_name="Cult Fit Candidate",
                commitment_type="subscription",
                frequency="monthly",
                estimated_amount=Decimal("2500.00"),
                min_amount=Decimal("2500.00"),
                max_amount=Decimal("2500.00"),
                occurrence_count=2,
                next_expected_date=dt.date.today() + dt.timedelta(days=10),
                confidence=Decimal("0.7500"),
                review_status="pending",
            )
        )
        db.commit()
    finally:
        db.close()

    ov2 = tc.post(
        "/api/v1/forecasting/generate",
        json={"horizon_days": 30, "force_refresh": True},
        headers=headers,
    ).json()
    # Variable bill unknown amount must NOT become 0.00 and must NOT inflate confirmed commitments
    comms = {c["name"]: c for c in ov2["commitments"]}
    assert "BESCOM Meter Variable" in comms
    assert comms["BESCOM Meter Variable"]["expected_amount"] is None
    assert comms["BESCOM Meter Variable"]["amount_certainty"] == "unknown_amount"
    assert ov2["cashflow"]["unknown_variable_commitments_count"] >= 1
    assert "Cult Fit Candidate (Candidate)" in comms
    assert comms["Cult Fit Candidate (Candidate)"]["commitment_status"] == "unconfirmed_candidate"
    # Confirmed total excludes candidate (2500.00)
    assert Decimal(str(ov2["cashflow"]["known_commitments_total"])) == Decimal("0.00")


def test_ledger_semantics_exclusions_commitments_and_no_side_effects(fc_client):
    tc, created_emails = fc_client
    headers = _register_and_login(tc, created_emails, "fc_sem")

    bank1 = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "HDFC Main", "account_type": "savings", "opening_balance": "120000.00"},
        headers=headers,
    ).json()
    bank2 = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "ICICI Reserve", "account_type": "savings", "opening_balance": "30000.00"},
        headers=headers,
    ).json()
    cc = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "HDFC Regalia Card", "account_type": "credit_card", "opening_balance": "10000.00"},
        headers=headers,
    ).json()

    cats = tc.get("/api/v1/finance/categories", headers=headers).json()
    cat_by_name = {c["name"]: c["id"] for c in cats}

    today = dt.date.today()

    def _add(acc_id, tx_type, amt, desc, cat_name, days_ago, source="manual"):
        r = tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc_id,
                "transaction_type": tx_type,
                "amount": amt,
                "currency": "INR",
                "description": desc,
                "category_id": cat_by_name.get(cat_name),
                "transaction_date": (today - dt.timedelta(days=days_ago)).isoformat(),
            },
            headers=headers,
        )
        assert r.status_code in (200, 201), r.text
        return r.json()

    # 3 months salary income
    for d in (75, 45, 15):
        _add(bank1["id"], "income", "90000.00", "ACME PAYROLL SALARY", "Salary", d)

    # Regular groceries & dining expenses + credit card expense
    for d in (80, 65, 50, 35, 20, 10, 4):
        _add(bank1["id"], "expense", "2000.00", "BIGBASKET GROCERIES", "Groceries", d)
    _add(cc["id"], "expense", "3000.00", "DINING OUT CARD", "Food & Dining", 12)

    # Internal transfer + credit card bill repayment MUST be excluded from spending & income!
    tr1 = tc.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": bank1["id"],
            "destination_account_id": bank2["id"],
            "amount": "25000.00",
            "transfer_date": (today - dt.timedelta(days=8)).isoformat(),
            "description": "Self transfer to ICICI",
        },
        headers=headers,
    )
    assert tr1.status_code in (200, 201), tr1.text

    # Reversed expense transaction MUST also be excluded cleanly
    rev_tx = _add(bank1["id"], "expense", "88000.00", "ACCIDENTAL ENTRY", "Shopping", 6)
    db = TestingSessionLocal()
    try:
        j = db.execute(
            select(LedgerJournal).where(LedgerJournal.transaction_id == uuid.UUID(rev_tx["id"]))
        ).scalar_one()
        j.is_reversed = True
        db.add(j)
        db.commit()
    finally:
        db.close()

    # Active subscription + upcoming Bill + Loan EMI in next 30 days
    sub_res = tc.post(
        "/api/v1/subscriptions",
        json={
            "subscription_name": "Netflix UHD",
            "category": "ott_streaming",
            "amount": "649.00",
            "billing_frequency": "monthly",
            "start_date": (today - dt.timedelta(days=20)).isoformat(),
            "next_renewal_date": (today + dt.timedelta(days=10)).isoformat(),
            "linked_account_id": bank1["id"],
        },
        headers=headers,
    )
    assert sub_res.status_code in (200, 201), sub_res.text

    loan_res = tc.post(
        "/api/v1/loans",
        json={
            "loan_name": "Car Loan",
            "lender_name": "HDFC Auto",
            "loan_type": "vehicle",
            "outstanding_principal": "300000.00",
            "interest_rate": "9.000",
            "loan_start_date": (today - dt.timedelta(days=30)).isoformat(),
            "tracking_start_date": (today - dt.timedelta(days=30)).isoformat(),
            "first_emi_date": (today + dt.timedelta(days=12)).isoformat(),
            "remaining_tenure_months": 36,
            "linked_repayment_account_id": bank1["id"],
        },
        headers=headers,
    )
    assert loan_res.status_code in (200, 201), loan_res.text
    emi_amt = Decimal(str(loan_res.json()["emi_amount"]))

    # Record transaction count & balances before forecasting
    txs_before = len(tc.get("/api/v1/finance/transactions", headers=headers).json()["items"])
    acc1_before = Decimal(str(tc.get(f"/api/v1/finance/accounts/{bank1['id']}", headers=headers).json()["current_balance"]))

    ov = tc.get("/api/v1/forecasting/overview?horizon_days=30", headers=headers).json()
    assert ov["forecast"]["status"] == "completed"
    assert ov["income"]["income_pattern"] == "regular_monthly"
    # Verify reversed 88k and transfer 25k did NOT pollute monthly average (~5,666/mo, nowhere near 30k+)
    assert Decimal(str(ov["expenses"]["historical_monthly_avg"])) < Decimal("15000.00")

    # Confirmed obligations must include Netflix (649) + Loan EMI (~9539)
    assert Decimal(str(ov["cashflow"]["known_commitments_total"])) == Decimal("649.00") + emi_amt

    # Liability account remains marked is_liability=True and NOT counted as positive bank cash
    bal_by_name = {b["account_name"]: b for b in ov["balances"]}
    assert bal_by_name["HDFC Regalia Card"]["is_liability"] is True
    assert bal_by_name["HDFC Main"]["is_liability"] is False

    # Forecasting must NEVER create transactions or modify balances
    txs_after = len(tc.get("/api/v1/finance/transactions", headers=headers).json()["items"])
    acc1_after = Decimal(str(tc.get(f"/api/v1/finance/accounts/{bank1['id']}", headers=headers).json()["current_balance"]))
    assert txs_after == txs_before
    assert acc1_after == acc1_before
    assert ForecastService().repo is not None
    assert ForecastRepository() is not None
    assert GenerateForecastRequest(horizon_days=30).horizon_days == 30
