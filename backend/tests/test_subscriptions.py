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
from app.models.subscriptions import (
    Subscription,
    SubscriptionCandidateDecision,
    SubscriptionPayment,
    SubscriptionPriceHistory,
)
from app.models.user import User
from app.services.bills.status_engine import resolve_user_today
from app.services.subscriptions.subscription_math import (
    advance_subscription_renewal,
    compute_monthly_and_annual_equivalent,
)
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
                cleanup_db.execute(
                    delete(SubscriptionCandidateDecision).where(
                        SubscriptionCandidateDecision.user_id == user.id
                    )
                )
                cleanup_db.execute(
                    delete(SubscriptionPayment).where(SubscriptionPayment.user_id == user.id)
                )
                cleanup_db.execute(
                    delete(SubscriptionPriceHistory).where(
                        SubscriptionPriceHistory.user_id == user.id
                    )
                )
                cleanup_db.execute(delete(Subscription).where(Subscription.user_id == user.id))
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
    tc: TestClient, headers: dict[str, str], name: str, opening_balance: str = "15000.00"
) -> dict:
    r = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": name,
            "account_type": "savings",
            "institution_name": "ICICI Bank",
            "opening_balance": opening_balance,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_subscription_math_normalization_and_calendar_renewals():
    # Monthly / Quarterly / Yearly / Missing price normalization
    m, a = compute_monthly_and_annual_equivalent(Decimal("1500.00"), "quarterly")
    assert m == Decimal("500.00") and a == Decimal("6000.00")

    m_y, a_y = compute_monthly_and_annual_equivalent(Decimal("1499.00"), "yearly")
    assert m_y == Decimal("124.92") and a_y == Decimal("1499.00")

    assert compute_monthly_and_annual_equivalent(None, "monthly") == (None, None)

    # Jan 31 -> Feb 28 (non-leap) -> Mar 31, and leap year Feb 29 -> Feb 28 next year
    feb = advance_subscription_renewal(dt.date(2025, 1, 31), "monthly", anchor_day=31)
    assert feb == dt.date(2025, 2, 28)
    assert advance_subscription_renewal(feb, "monthly", anchor_day=31) == dt.date(2025, 3, 31)
    assert advance_subscription_renewal(dt.date(2024, 2, 29), "yearly", anchor_day=29) == dt.date(
        2025, 2, 28
    )


def test_subscription_lifecycle_price_history_payments_reminders_and_isolation(
    live_client, monkeypatch
):
    tc, created = live_client
    h_a = _register_and_login(tc, created, "sub_a", "Ananya Verma")
    today_ist = resolve_user_today("Asia/Kolkata")
    savings = _create_account(tc, h_a, "ICICI Savings", "10000.00")

    # 1. Create active Netflix subscription (₹199/mo) & trial Cloud subscription with missing price (stays None)
    r_nf = tc.post(
        "/api/v1/subscriptions",
        json={
            "subscription_name": "Netflix Mobile",
            "provider_name": "Netflix",
            "category": "ott_streaming",
            "plan_name": "Mobile",
            "amount": "199.00",
            "billing_frequency": "monthly",
            "start_date": today_ist.isoformat(),
            "next_renewal_date": (today_ist + dt.timedelta(days=3)).isoformat(),
            "reminder_days_before": [3, 1, 0],
        },
        headers=h_a,
    )
    assert r_nf.status_code == 201, r_nf.text
    nf = r_nf.json()
    assert Decimal(nf["monthly_equivalent"]) == Decimal("199.00")
    assert Decimal(nf["annual_equivalent"]) == Decimal("2388.00")
    assert len(nf["price_history"]) == 1

    r_tr = tc.post(
        "/api/v1/subscriptions",
        json={
            "subscription_name": "Adobe Creative Cloud Trial",
            "provider_name": "Adobe",
            "category": "software_saas",
            "is_trial": True,
            "start_date": (today_ist - dt.timedelta(days=5)).isoformat(),
            "trial_start_date": (today_ist - dt.timedelta(days=5)).isoformat(),
            "trial_end_date": today_ist.isoformat(),
            "billing_frequency": "yearly",
            "reminder_days_before": [1, 0],
        },
        headers=h_a,
    )
    assert r_tr.status_code == 201, r_tr.text
    trial_sub = r_tr.json()
    assert trial_sub["status"] == "trial"
    assert trial_sub["amount"] is None
    assert trial_sub["is_amount_unknown"] is True

    # 2. Trial reminder fires cleanly via Phase 5 ReminderService
    monkeypatch.setattr(settings, "SMTP_ENABLED", False)
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    rem_proc = tc.post("/api/v1/bills/reminders/process", headers=h_a)
    assert rem_proc.status_code == 200
    assert rem_proc.json()["notifications_created"] >= 1
    notifs = tc.get("/api/v1/notifications").json()["items"]
    assert any(n["notification_type"] == "subscription_trial_ending" for n in notifs)

    # 3. Record Netflix payment at old price ₹199 -> updates ledger & analytics without auto-paying renewals
    idem = f"sub-pay-{uuid.uuid4().hex}"
    pay1 = tc.post(
        f"/api/v1/subscriptions/{nf['id']}/payments",
        json={
            "amount_paid": "199.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "upi",
            "idempotency_key": idem,
        },
        headers=h_a,
    )
    assert pay1.status_code == 200, pay1.text
    assert len(pay1.json()["payments"]) == 1

    # Idempotency check: duplicate key does NOT create duplicate transaction
    pay_dup = tc.post(
        f"/api/v1/subscriptions/{nf['id']}/payments",
        json={
            "amount_paid": "199.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "upi",
            "idempotency_key": idem,
        },
        headers=h_a,
    )
    assert pay_dup.status_code == 200
    assert len(pay_dup.json()["payments"]) == 1

    # 4. Record Price Increase ₹199 -> ₹249: past payment preserved at ₹199, projections rise to ₹249
    pc = tc.post(
        f"/api/v1/subscriptions/{nf['id']}/price-change",
        json={
            "new_price": "249.00",
            "effective_date": (today_ist + dt.timedelta(days=1)).isoformat(),
            "reason": "Standard tariff hike",
        },
        headers=h_a,
    )
    assert pc.status_code == 200, pc.text
    nf_updated = pc.json()
    assert Decimal(nf_updated["amount"]) == Decimal("249.00")
    assert Decimal(nf_updated["total_actual_paid"]) == Decimal("199.00")
    assert len(nf_updated["price_history"]) == 2

    # Phase 4 Analytics shows ₹199 actual spend (NOT future ₹249 projection!)
    dash = tc.get("/api/v1/analytics/dashboard", params={"period": "this_month"}).json()
    assert Decimal(dash["total_expenses"]) == Decimal("199.00")

    # 5. Pause removes from active recurring cost totals; Resume restores; Cancel stops reminders & zeroes projection
    tc.post(f"/api/v1/subscriptions/{nf['id']}/pause", headers=h_a)
    ov_paused = tc.get("/api/v1/subscriptions/overview").json()
    assert Decimal(ov_paused["monthly_recurring_cost"]) == Decimal("0.00")
    assert ov_paused["paused_count"] == 1

    tc.post(f"/api/v1/subscriptions/{nf['id']}/resume", headers=h_a)
    ov_resumed = tc.get("/api/v1/subscriptions/overview").json()
    assert Decimal(ov_resumed["monthly_recurring_cost"]) == Decimal("249.00")

    # Reversing payment restores bank balance cleanly
    p_id = nf_updated["payments"][0]["id"]
    rev = tc.post(
        f"/api/v1/subscriptions/{nf['id']}/payments/{p_id}/reverse",
        json={"reason": "Recorded duplicate entry"},
        headers=h_a,
    )
    assert rev.status_code == 200
    assert rev.json()["payments"][0]["payment_status"] == "reversed"
    assert Decimal(tc.get("/api/v1/finance/accounts").json()[0]["current_balance"]) == Decimal(
        "10000.00"
    )

    # Cancel subscription stops all future pending/failed reminders (delivered audit rows remain intact)
    canc = tc.post(
        f"/api/v1/subscriptions/{nf['id']}/cancel",
        json={"cancellation_date": today_ist.isoformat()},
        headers=h_a,
    )
    assert canc.status_code == 200
    assert canc.json()["status"] == "cancelled"
    assert all(r["delivery_status"] not in {"pending", "failed"} for r in canc.json()["reminders"])

    # 6. Cross-user IDOR + CSRF + 401 checks
    no_csrf = tc.post(
        "/api/v1/subscriptions",
        json={
            "subscription_name": "Blocked",
            "start_date": today_ist.isoformat(),
            "billing_frequency": "monthly",
        },
    )
    assert no_csrf.status_code == 403

    with TestClient(tc.app, raise_server_exceptions=False) as tc_b:
        h_b = _register_and_login(tc_b, created, "sub_b", "User B")
        assert tc_b.get(f"/api/v1/subscriptions/{nf['id']}").status_code == 404
        assert (
            tc_b.post(f"/api/v1/subscriptions/{nf['id']}/cancel", headers=h_b).status_code == 404
        )
        assert tc_b.get("/api/v1/subscriptions").json()["total"] == 0

    with TestClient(tc.app) as anon:
        assert anon.get("/api/v1/subscriptions").status_code == 401


def test_subscription_candidate_detection_excludes_utilities_and_respects_decisions(live_client):
    tc, created = live_client
    headers = _register_and_login(tc, created, "sub_cand", "Kabir Menon")
    acc = _create_account(tc, headers, "HDFC Bank", "50000.00")

    # Seed 2 monthly Spotify charges (candidate!) and 2 monthly BESCOM Electricity charges (excluded bill!)
    for d in ("2026-10-05", "2026-11-05"):
        tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc["id"],
                "transaction_type": "expense",
                "amount": "119.00",
                "description": "Spotify Premium AutoPay",
                "merchant_payee": "Spotify India",
                "transaction_date": d,
            },
            headers=headers,
        )
        tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc["id"],
                "transaction_type": "expense",
                "amount": "1800.00",
                "description": "BESCOM Electricity Bill",
                "merchant_payee": "BESCOM",
                "transaction_date": d,
            },
            headers=headers,
        )

    cands = tc.get("/api/v1/subscriptions/candidates").json()
    assert len(cands) == 1
    assert cands[0]["detected_frequency"] == "monthly"
    assert Decimal(cands[0]["estimated_amount"]) == Decimal("119.00")

    # Ignore candidate persists across reloads
    dec = tc.post(
        "/api/v1/subscriptions/candidates/decision",
        json={"merchant_key": cands[0]["merchant_key"], "action": "ignore"},
        headers=headers,
    )
    assert dec.status_code == 200
    assert tc.get("/api/v1/subscriptions/candidates").json() == []
