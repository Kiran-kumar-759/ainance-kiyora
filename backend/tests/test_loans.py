import datetime as dt
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.bills import BillReminder, Notification
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.loans import (
    Loan,
    LoanInstallment,
    LoanInterestRateHistory,
    LoanPayment,
)
from app.models.user import User
from app.services.bills.status_engine import resolve_user_today
from app.services.loans.emi_engine import calculate_emi_summary, generate_amortization_schedule
from tests.conftest import TestingSessionLocal


@pytest.fixture
def live_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    created_emails: list[str] = []
    app = create_application()

    def real_style_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = real_style_get_db

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, created_emails

    app.dependency_overrides.clear()

    cleanup_db = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                cleanup_db.execute(delete(Notification).where(Notification.user_id == user.id))
                cleanup_db.execute(delete(BillReminder).where(BillReminder.user_id == user.id))
                cleanup_db.execute(delete(LoanPayment).where(LoanPayment.user_id == user.id))
                cleanup_db.execute(
                    delete(LoanInterestRateHistory).where(
                        LoanInterestRateHistory.user_id == user.id
                    )
                )
                cleanup_db.execute(delete(LoanInstallment).where(LoanInstallment.user_id == user.id))
                cleanup_db.execute(delete(Loan).where(Loan.user_id == user.id))
                acc_ids = list(
                    cleanup_db.execute(
                        select(FinancialAccount.id).where(FinancialAccount.user_id == user.id)
                    ).scalars()
                )
                if acc_ids:
                    cleanup_db.execute(
                        delete(LedgerEntry).where(LedgerEntry.account_id.in_(acc_ids))
                    )
                cleanup_db.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
                cleanup_db.execute(
                    delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id)
                )
                cleanup_db.execute(
                    delete(FinancialTransfer).where(FinancialTransfer.user_id == user.id)
                )
                cleanup_db.execute(
                    delete(FinancialAccount).where(FinancialAccount.user_id == user.id)
                )
                cleanup_db.execute(
                    delete(FinancialCategory).where(FinancialCategory.user_id == user.id)
                )
                cleanup_db.delete(user)
        cleanup_db.commit()
    finally:
        cleanup_db.close()


def _register_and_login(
    tc: TestClient, created_emails: list[str], prefix: str, name: str
) -> dict[str, str]:
    rate_limiter.clear()
    email = f"{prefix}.{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    reg = tc.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201, reg.text
    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200, login.text
    csrf = login.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf is not None
    return {"X-CSRF-Token": csrf}


def _create_account(
    tc: TestClient, headers: dict[str, str], name: str, opening_balance: str = "200000.00"
) -> dict:
    r = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": name,
            "account_type": "savings",
            "institution_name": "SBI",
            "opening_balance": opening_balance,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_deterministic_emi_math_zero_interest_and_month_end_schedule():
    # Reducing balance: ₹5,00,000 at 9% p.a. for 60 months -> ₹10,379.18
    emi, tot_int, tot_rep, _ = calculate_emi_summary(
        Decimal("500000.00"), Decimal("9.000"), 60, "monthly", "reducing_balance"
    )
    assert emi == Decimal("10379.18")
    assert tot_rep == Decimal("500000.00") + tot_int

    # Zero-interest loan
    emi0, int0, rep0, _ = calculate_emi_summary(
        Decimal("120000.00"), Decimal("0.000"), 12, "monthly", "zero_interest"
    )
    assert emi0 == Decimal("10000.00") and int0 == Decimal("0.00") and rep0 == Decimal("120000.00")

    # Amortization reconciliation + month-end 31st + leap year Feb 29
    sched = generate_amortization_schedule(
        opening_principal=Decimal("100000.00"),
        annual_interest_rate=Decimal("10.000"),
        periods=12,
        first_due_date=dt.date(2024, 1, 31),
        anchor_day=31,
    )
    assert len(sched) == 12
    assert sched[1].due_date == dt.date(2024, 2, 29)  # Leap year handled
    assert sched[2].due_date == dt.date(2024, 3, 31)  # Anchor day 31 preserved
    assert sched[-1].closing_principal == Decimal("0.00")
    assert sum(row.principal_component for row in sched) == Decimal("100000.00")


def test_loan_accounting_split_principal_interest_and_analytics_accuracy(live_client):
    tc, created = live_client
    headers = _register_and_login(tc, created, "loan_acct", "Siddharth Joshi")
    today_ist = resolve_user_today("Asia/Kolkata")
    savings = _create_account(tc, headers, "SBI Main Savings", "100000.00")

    # Register existing home/car loan mid-tenure (₹1,50,000 outstanding out of ₹2,00,000 original)
    r_loan = tc.post(
        "/api/v1/loans",
        json={
            "loan_name": "HDFC Car Loan",
            "lender_name": "HDFC Bank",
            "loan_type": "vehicle",
            "original_principal": "200000.00",
            "outstanding_principal": "150000.00",
            "interest_rate": "9.500",
            "interest_rate_type": "floating",
            "calculation_method": "reducing_balance",
            "loan_start_date": "2025-11-01",
            "tracking_start_date": today_ist.isoformat(),
            "first_emi_date": today_ist.isoformat(),
            "original_tenure_months": 24,
            "remaining_tenure_months": 12,
            "linked_repayment_account_id": savings["id"],
        },
        headers=headers,
    )
    assert r_loan.status_code == 201, r_loan.text
    loan = r_loan.json()
    assert Decimal(loan["current_outstanding_principal"]) == Decimal("150000.00")
    assert len(loan["installments"]) == 12

    # Net financial position: ₹1,00,000 asset - ₹1,50,000 loan liability = -₹50,000
    fin_dash_before = tc.get("/api/v1/finance/dashboard").json()
    assert Decimal(fin_dash_before["total_assets"]) == Decimal("100000.00")
    assert Decimal(fin_dash_before["total_liabilities"]) == Decimal("150000.00")
    assert Decimal(fin_dash_before["net_financial_position"]) == Decimal("-50000.00")

    # Record EMI payment split: ₹12,000 Principal + ₹3,000 Interest = ₹15,000 cash outflow
    idem = f"emi-{uuid.uuid4().hex}"
    pay = tc.post(
        f"/api/v1/loans/{loan['id']}/payments",
        json={
            "payment_type": "emi",
            "payment_date": today_ist.isoformat(),
            "payment_account_id": savings["id"],
            "installment_id": loan["installments"][0]["id"],
            "principal_paid": "12000.00",
            "interest_paid": "3000.00",
            "idempotency_key": idem,
        },
        headers=headers,
    )
    assert pay.status_code == 200, pay.text
    paid_loan = pay.json()
    assert Decimal(paid_loan["current_outstanding_principal"]) == Decimal("138000.00")
    assert Decimal(paid_loan["total_principal_repaid"]) == Decimal("12000.00")
    assert Decimal(paid_loan["total_interest_paid"]) == Decimal("3000.00")
    assert paid_loan["installments"][0]["status"] == "paid"

    # Idempotency check: repeating same idempotency_key does not double deduct
    pay_dup = tc.post(
        f"/api/v1/loans/{loan['id']}/payments",
        json={
            "payment_type": "emi",
            "payment_date": today_ist.isoformat(),
            "payment_account_id": savings["id"],
            "principal_paid": "12000.00",
            "interest_paid": "3000.00",
            "idempotency_key": idem,
        },
        headers=headers,
    )
    assert pay_dup.status_code == 200
    assert Decimal(pay_dup.json()["current_outstanding_principal"]) == Decimal("138000.00")

    # Verify SBI Savings dropped by full ₹15,000 (₹85,000) & Loan Liability dropped by ₹12,000 (₹1,38,000)
    accounts = {a["id"]: a for a in tc.get("/api/v1/finance/accounts").json()}
    assert Decimal(accounts[savings["id"]]["current_balance"]) == Decimal("85000.00")
    assert Decimal(accounts[loan["liability_account_id"]]["current_balance"]) == Decimal("138000.00")

    # CRITICAL SECTION 5.6 CHECK: Phase 4 Analytics counts ONLY ₹3,000 interest as expense, NEVER ₹15,000!
    analytics_dash = tc.get("/api/v1/analytics/dashboard", params={"period": "this_month"}).json()
    assert Decimal(analytics_dash["total_expenses"]) == Decimal("3000.00")
    assert Decimal(analytics_dash["total_income"]) == Decimal("0.00")

    # Principal > remaining principal must fail atomically
    bad_pay = tc.post(
        f"/api/v1/loans/{loan['id']}/payments",
        json={
            "payment_type": "prepayment",
            "payment_date": today_ist.isoformat(),
            "payment_account_id": savings["id"],
            "principal_paid": "500000.00",
            "interest_paid": "0.00",
        },
        headers=headers,
    )
    assert bad_pay.status_code == 400

    # Reversing payment restores bank ₹1,00,000 and loan ₹1,50,000 cleanly
    p_id = paid_loan["payments"][0]["id"]
    rev = tc.post(
        f"/api/v1/loans/{loan['id']}/payments/{p_id}/reverse",
        json={"reason": "Correction reversal"},
        headers=headers,
    )
    assert rev.status_code == 200
    assert Decimal(rev.json()["current_outstanding_principal"]) == Decimal("150000.00")
    assert Decimal(
        tc.get(f"/api/v1/finance/accounts/{savings['id']}").json()["current_balance"]
    ) == Decimal("100000.00")


def test_loan_rate_revision_prepayment_scenario_foreclosure_disbursement_and_isolation(
    live_client, monkeypatch
):
    tc, created = live_client
    h_a = _register_and_login(tc, created, "loan_adv", "Priya Sharma")
    today_ist = resolve_user_today("Asia/Kolkata")
    savings = _create_account(tc, h_a, "HDFC Savings", "50000.00")

    # Create newly disbursed personal loan (₹50,000 credited to HDFC Savings -> NOT counted as income!)
    r_loan = tc.post(
        "/api/v1/loans",
        json={
            "loan_name": "Personal Loan",
            "lender_name": "Bajaj Finserv",
            "loan_type": "personal",
            "original_principal": "50000.00",
            "outstanding_principal": "50000.00",
            "interest_rate": "12.000",
            "interest_rate_type": "floating",
            "calculation_method": "reducing_balance",
            "loan_start_date": today_ist.isoformat(),
            "tracking_start_date": today_ist.isoformat(),
            "first_emi_date": today_ist.isoformat(),
            "original_tenure_months": 12,
            "remaining_tenure_months": 12,
            "record_disbursement_to_account_id": savings["id"],
            "reminder_days_before": [0],
        },
        headers=h_a,
    )
    assert r_loan.status_code == 201, r_loan.text
    loan = r_loan.json()

    # Savings went ₹50k -> ₹1,00k, loan liability is ₹50k, Income in Analytics is STILL ₹0.00!
    assert Decimal(
        tc.get(f"/api/v1/finance/accounts/{savings['id']}").json()["current_balance"]
    ) == Decimal("100000.00")
    assert Decimal(
        tc.get("/api/v1/analytics/dashboard", params={"period": "this_month"}).json()["total_income"]
    ) == Decimal("0.00")

    # EMI reminder triggers via Phase 5 Notification system
    monkeypatch.setattr(settings, "SMTP_ENABLED", False)
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    rem = tc.post("/api/v1/bills/reminders/process", headers=h_a)
    assert rem.json()["notifications_created"] >= 1
    assert any(
        n["notification_type"] == "loan_emi_due"
        for n in tc.get("/api/v1/notifications").json()["items"]
    )

    # Floating interest rate hike 12% -> 14% updates future installments & preserves rate history
    rev_r = tc.post(
        f"/api/v1/loans/{loan['id']}/rate-revision",
        json={
            "new_rate": "14.000",
            "effective_date": today_ist.isoformat(),
            "policy": "recalculate_emi",
            "reason": "RBI Repo Rate adjustment",
        },
        headers=h_a,
    )
    assert rev_r.status_code == 200, rev_r.text
    assert len(rev_r.json()["rate_history"]) == 2
    assert Decimal(rev_r.json()["emi_amount"]) > Decimal(loan["emi_amount"])

    # Hypothetical prepayment scenario NEVER modifies DB balances
    sim = tc.post(
        f"/api/v1/loans/{loan['id']}/prepayment-scenario",
        json={
            "extra_monthly_emi": "1000.00",
            "lump_sum_prepayment": "20000.00",
            "prepayment_mode": "reduce_tenure",
            "user_prepayment_fee": "500.00",
        },
        headers=h_a,
    )
    assert sim.status_code == 200, sim.text
    sim_data = sim.json()
    assert sim_data["is_scenario_simulation"] is True
    assert Decimal(sim_data["estimated_interest_saved"]) > Decimal("0.00")
    assert Decimal(
        tc.get(f"/api/v1/loans/{loan['id']}").json()["current_outstanding_principal"]
    ) == Decimal("50000.00")

    # Confirmed prepayment + foreclosure closes loan cleanly and cancels pending reminders
    foreclose = tc.post(
        f"/api/v1/loans/{loan['id']}/payments",
        json={
            "payment_type": "foreclosure",
            "payment_date": today_ist.isoformat(),
            "payment_account_id": savings["id"],
            "principal_paid": "50000.00",
            "interest_paid": "0.00",
            "fee_paid": "500.00",
        },
        headers=h_a,
    )
    assert foreclose.status_code == 200, foreclose.text
    closed = foreclose.json()
    assert closed["status"] == "closed"
    assert Decimal(closed["current_outstanding_principal"]) == Decimal("0.00")
    assert all(r["delivery_status"] not in {"pending", "failed"} for r in closed["reminders"])

    # Cross-user IDOR + CSRF + 401
    assert (
        tc.post(
            "/api/v1/loans",
            json={
                "loan_name": "No CSRF",
                "lender_name": "SBI",
                "outstanding_principal": "10000.00",
                "interest_rate": "8.0",
                "loan_start_date": today_ist.isoformat(),
                "tracking_start_date": today_ist.isoformat(),
                "first_emi_date": today_ist.isoformat(),
                "remaining_tenure_months": 12,
            },
        ).status_code
        == 403
    )
    with TestClient(tc.app, raise_server_exceptions=False) as tc_b:
        h_b = _register_and_login(tc_b, created, "loan_b", "User B")
        assert tc_b.get(f"/api/v1/loans/{loan['id']}").status_code == 404
        assert tc_b.post(f"/api/v1/loans/{loan['id']}/archive", headers=h_b).status_code == 404
        assert tc_b.get("/api/v1/loans").json()["total"] == 0
    with TestClient(tc.app) as anon:
        assert anon.get("/api/v1/loans").status_code == 401
