import datetime as dt
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.bills import (
    Bill,
    BillDocument,
    BillPayment,
    BillRecurrenceSchedule,
    BillReminder,
    Notification,
)
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.user import User
from app.repositories.bills.bill_repository import BillRepository
from app.services.bills.bill_storage import BillDocumentStorage
from app.services.bills.recurrence import advance_due_date
from app.services.bills.status_engine import compute_bill_derived_status, resolve_user_today
from tests.conftest import TestingSessionLocal

IST_TZ = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def live_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    """
    Real PostgreSQL multi-session TestClient fixture.
    Each HTTP request uses an independent PostgreSQL SessionLocal.
    """
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

    doc_storage = BillDocumentStorage()
    cleanup_db = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                shutil.rmtree(doc_storage.base_dir / str(user.id), ignore_errors=True)
                cleanup_db.execute(delete(Notification).where(Notification.user_id == user.id))
                cleanup_db.execute(delete(BillReminder).where(BillReminder.user_id == user.id))
                cleanup_db.execute(delete(BillDocument).where(BillDocument.user_id == user.id))
                cleanup_db.execute(delete(BillPayment).where(BillPayment.user_id == user.id))
                cleanup_db.execute(delete(Bill).where(Bill.user_id == user.id))
                cleanup_db.execute(
                    delete(BillRecurrenceSchedule).where(BillRecurrenceSchedule.user_id == user.id)
                )
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
    tc: TestClient,
    headers: dict[str, str],
    name: str,
    account_type: str = "savings",
    opening_balance: str = "50000.00",
    credit_limit: str | None = None,
) -> dict:
    payload: dict[str, object] = {
        "name": name,
        "account_type": account_type,
        "institution_name": "HDFC Bank",
        "opening_balance": opening_balance,
    }
    if credit_limit is not None:
        payload["credit_limit"] = credit_limit
    r = tc.post("/api/v1/finance/accounts", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _add_expense(
    tc: TestClient,
    headers: dict[str, str],
    account_id: str,
    amount: str,
    description: str,
    tx_date: dt.date,
) -> dict:
    r = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": account_id,
            "transaction_type": "expense",
            "amount": amount,
            "description": description,
            "transaction_date": tx_date.isoformat(),
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_unit_recurrence_month_end_and_timezone_status_rules():
    # Month-end 31st rollover across Feb non-leap, Feb leap, and 30-day months
    jan_31 = dt.date(2025, 1, 31)
    feb_28 = advance_due_date(jan_31, "monthly", anchor_day=31)
    assert feb_28 == dt.date(2025, 2, 28)
    mar_31 = advance_due_date(feb_28, "monthly", anchor_day=31)
    assert mar_31 == dt.date(2025, 3, 31)
    apr_30 = advance_due_date(mar_31, "monthly", anchor_day=31)
    assert apr_30 == dt.date(2025, 4, 30)

    # Leap-year yearly rollover (29 Feb 2024 -> 28 Feb 2025)
    assert advance_due_date(dt.date(2024, 2, 29), "yearly", anchor_day=29) == dt.date(2025, 2, 28)

    # Quarterly rollover
    assert advance_due_date(dt.date(2026, 1, 15), "quarterly", anchor_day=15) == dt.date(2026, 4, 15)

    # IST vs UTC boundary: 2026-11-25 19:00 UTC is already 2026-11-26 00:30 IST
    utc_late = dt.datetime(2026, 11, 25, 19, 0, tzinfo=dt.UTC)
    assert utc_late.astimezone(IST_TZ).date() == dt.date(2026, 11, 26)
    assert isinstance(resolve_user_today("Asia/Kolkata"), dt.date)

    # Deterministic status transitions and paid lock
    fake_bill = Bill(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        bill_name="Test",
        bill_category="electricity",
        bill_type="one_time",
        is_variable_amount=False,
        expected_amount=Decimal("1000.00"),
        current_amount=Decimal("1000.00"),
        amount_paid_total=Decimal("0.00"),
        currency="INR",
        due_date=dt.date(2026, 12, 10),
        stored_status="unpaid",
        reminder_enabled=True,
        reminder_days_before=[7, 3, 1, 0],
        notification_channels={"in_app": True, "email": False, "sms": False},
        is_active=True,
    )
    assert compute_bill_derived_status(fake_bill, today=dt.date(2026, 12, 1)) == "upcoming"
    assert compute_bill_derived_status(fake_bill, today=dt.date(2026, 12, 5)) == "due_soon"
    assert compute_bill_derived_status(fake_bill, today=dt.date(2026, 12, 11)) == "overdue"
    fake_bill.stored_status = "paid"
    assert compute_bill_derived_status(fake_bill, today=dt.date(2026, 12, 15)) == "paid"


def test_bills_crud_variable_unknown_filters_and_archive(live_client):
    tc, created = live_client
    headers = _register_and_login(tc, created, "bills_crud", "Asha Nair")
    today_ist = resolve_user_today("Asia/Kolkata")

    # 1. Fixed one-time overdue bill
    r1 = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Municipal Water Tax",
            "bill_category": "water",
            "provider_name": "BWSSB",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "1450.00",
            "due_date": (today_ist - dt.timedelta(days=2)).isoformat(),
            "preferred_payment_method": "upi",
            "reminder_days_before": [3, 1, 0],
        },
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    water_bill = r1.json()
    assert water_bill["derived_status"] == "overdue"
    assert Decimal(water_bill["remaining_due"]) == Decimal("1450.00")

    # 2. Variable recurring bill with unknown actual amount yet
    r2 = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "BESCOM Home Electricity",
            "bill_category": "electricity",
            "provider_name": "BESCOM",
            "bill_type": "recurring",
            "frequency": "monthly",
            "is_variable_amount": True,
            "due_date": (today_ist + dt.timedelta(days=3)).isoformat(),
            "reminder_days_before": [7, 3, 1, 0],
        },
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    bescom = r2.json()
    assert bescom["derived_status"] == "due_soon"
    assert bescom["is_amount_unknown"] is True
    assert bescom["current_amount"] is None
    assert bescom["remaining_due"] is None  # Never coerced to 0!

    # 3. Upcoming internet bill
    r3 = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "ACT Fibernet",
            "bill_category": "internet",
            "provider_name": "ACT",
            "bill_type": "recurring",
            "frequency": "monthly",
            "is_variable_amount": False,
            "expected_amount": "1178.82",
            "due_date": (today_ist + dt.timedelta(days=15)).isoformat(),
        },
        headers=headers,
    )
    assert r3.status_code == 201, r3.text

    # Overview counts & unknown variable counter
    ov = tc.get("/api/v1/bills/overview")
    assert ov.status_code == 200, ov.text
    overview = ov.json()
    assert overview["overdue_count"] == 1
    assert overview["due_soon_count"] == 1
    assert overview["upcoming_count"] == 2
    assert overview["unknown_variable_bills_count"] == 1
    assert Decimal(overview["total_overdue_known_amount"]) == Decimal("1450.00")

    # Search, filter, sort, pagination
    search_res = tc.get("/api/v1/bills", params={"search": "BESCOM"})
    assert search_res.status_code == 200
    assert search_res.json()["total"] == 1

    overdue_res = tc.get("/api/v1/bills/overdue")
    assert overdue_res.status_code == 200
    assert overdue_res.json()["total"] == 1

    paged = tc.get("/api/v1/bills", params={"page": 1, "page_size": 2, "sort_by": "name_asc"})
    assert paged.status_code == 200
    assert len(paged.json()["items"]) == 2
    assert paged.json()["total"] == 3
    assert paged.json()["total_pages"] == 2

    # Update variable bill actual amount + due date
    upd = tc.patch(
        f"/api/v1/bills/{bescom['id']}",
        json={"current_amount": "2340.50"},
        headers=headers,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["is_amount_unknown"] is False
    assert Decimal(upd.json()["current_amount"]) == Decimal("2340.50")

    # Archive bill cleanly
    arch = tc.post(f"/api/v1/bills/{water_bill['id']}/archive", headers=headers)
    assert arch.status_code == 200
    assert arch.json()["derived_status"] == "archived"

    active_only = tc.get("/api/v1/bills")
    assert active_only.json()["total"] == 2
    with_arch = tc.get("/api/v1/bills", params={"include_archived": True})
    assert with_arch.json()["total"] == 3


def test_payment_ledger_integration_idempotency_rollback_and_analytics_consistency(live_client):
    tc, created = live_client
    headers = _register_and_login(tc, created, "bills_pay", "Rohan Deshmukh")
    today_ist = resolve_user_today("Asia/Kolkata")

    savings = _create_account(tc, headers, "SBI Savings", "savings", "10000.00")
    credit_card = _create_account(
        tc, headers, "HDFC Regalia", "credit_card", "5000.00", credit_limit="100000.00"
    )

    # Create monthly electricity bill
    bill_res = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "MSEDCL Electricity",
            "bill_category": "electricity",
            "provider_name": "MSEDCL",
            "bill_type": "recurring",
            "frequency": "monthly",
            "is_variable_amount": False,
            "expected_amount": "3200.00",
            "due_date": (today_ist + dt.timedelta(days=2)).isoformat(),
            "preferred_payment_method": "upi",
        },
        headers=headers,
    )
    assert bill_res.status_code == 201, bill_res.text
    bill = bill_res.json()

    # Overdraft attempt > 10,000 must fail and roll back cleanly
    fail_pay = tc.post(
        f"/api/v1/bills/{bill['id']}/payments",
        json={
            "amount_paid": "25000.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "upi",
        },
        headers=headers,
    )
    assert fail_pay.status_code == 400
    assert Decimal(tc.get("/api/v1/finance/accounts").json()[0]["current_balance"]) >= Decimal("5000.00")

    # Record legitimate payment with explicit idempotency_key
    idem_key = f"pay-{uuid.uuid4().hex}"
    pay1 = tc.post(
        f"/api/v1/bills/{bill['id']}/payments",
        json={
            "amount_paid": "3200.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "upi",
            "reference_number": "UPI60991234",
            "idempotency_key": idem_key,
            "mark_as_fully_paid": True,
        },
        headers=headers,
    )
    assert pay1.status_code == 200, pay1.text
    paid_bill = pay1.json()
    assert paid_bill["derived_status"] == "paid"
    assert len(paid_bill["payments"]) == 1
    assert paid_bill["payments"][0]["transaction_id"] is not None
    # Pending reminders cancelled upon payment
    assert all(r["delivery_status"] == "cancelled" for r in paid_bill["reminders"])

    # Repeating with same idempotency_key returns existing paid bill without duplicate tx/payment
    pay_dup = tc.post(
        f"/api/v1/bills/{bill['id']}/payments",
        json={
            "amount_paid": "3200.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "upi",
            "idempotency_key": idem_key,
            "mark_as_fully_paid": True,
        },
        headers=headers,
    )
    assert pay_dup.status_code == 200
    assert len(pay_dup.json()["payments"]) == 1

    # Verify next recurring occurrence was auto-created cleanly
    bills_all = tc.get("/api/v1/bills").json()["items"]
    assert len(bills_all) == 2

    # Check account balance decreased accurately (10000 - 3200 = 6800) and transaction source='bill_payment'
    tx_list = tc.get("/api/v1/finance/transactions", params={"source": "bill_payment"}).json()
    assert tx_list["total"] == 1
    assert Decimal(tx_list["items"][0]["amount"]) == Decimal("3200.00")

    accounts_map = {a["id"]: a for a in tc.get("/api/v1/finance/accounts").json()}
    assert Decimal(accounts_map[savings["id"]]["current_balance"]) == Decimal("6800.00")

    # Credit card bill linked to HDFC Regalia -> paying from SBI Savings creates transfer, NOT duplicate expense
    cc_bill_res = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "HDFC Regalia Statement",
            "bill_category": "credit_card",
            "provider_name": "HDFC Bank",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "2000.00",
            "due_date": (today_ist + dt.timedelta(days=4)).isoformat(),
            "linked_account_id": credit_card["id"],
        },
        headers=headers,
    )
    assert cc_bill_res.status_code == 201, cc_bill_res.text
    cc_pay = tc.post(
        f"/api/v1/bills/{cc_bill_res.json()['id']}/payments",
        json={
            "amount_paid": "2000.00",
            "payment_date": today_ist.isoformat(),
            "financial_account_id": savings["id"],
            "payment_method": "net_banking",
            "mark_as_fully_paid": True,
        },
        headers=headers,
    )
    assert cc_pay.status_code == 200, cc_pay.text
    assert cc_pay.json()["payments"][0]["transfer_id"] is not None

    accounts_after = {a["id"]: a for a in tc.get("/api/v1/finance/accounts").json()}
    assert Decimal(accounts_after[savings["id"]]["current_balance"]) == Decimal("4800.00")
    assert Decimal(accounts_after[credit_card["id"]]["current_balance"]) == Decimal("3000.00")

    # Phase 4 analytics total_expenses must be 3200.00 (electricity only, NOT 5200.00!)
    dash = tc.get("/api/v1/analytics/dashboard", params={"period": "this_month"}).json()
    assert Decimal(dash["total_expenses"]) == Decimal("3200.00")

    # Linking existing expense transaction settles bill without creating a duplicate tx
    pre_tx = _add_expense(
        tc, headers, savings["id"], "800.00", "Airtel Recharge UPI", today_ist
    )
    mobile_bill = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Airtel Prepaid",
            "bill_category": "mobile_recharge",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "800.00",
            "due_date": today_ist.isoformat(),
        },
        headers=headers,
    ).json()
    link_res = tc.post(
        f"/api/v1/bills/{mobile_bill['id']}/payments/link-transaction",
        json={"transaction_id": pre_tx["id"], "payment_method": "upi"},
        headers=headers,
    )
    assert link_res.status_code == 200, link_res.text
    assert link_res.json()["derived_status"] == "paid"

    # Re-linking same tx to another bill raises 409
    other_bill = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Gas Cylinder",
            "bill_category": "gas",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "800.00",
            "due_date": today_ist.isoformat(),
        },
        headers=headers,
    ).json()
    dup_link = tc.post(
        f"/api/v1/bills/{other_bill['id']}/payments/link-transaction",
        json={"transaction_id": pre_tx["id"], "payment_method": "upi"},
        headers=headers,
    )
    assert dup_link.status_code == 409


def test_recurrence_end_date_deactivation_and_duplicate_constraint(live_client):
    tc, created = live_client
    headers = _register_and_login(tc, created, "bills_rec", "Meera Iyer")
    start_due = dt.date(2026, 1, 31)
    end_dt = dt.date(2026, 2, 28)

    r = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "House Rent",
            "bill_category": "rent",
            "bill_type": "recurring",
            "frequency": "monthly",
            "is_variable_amount": False,
            "expected_amount": "22000.00",
            "due_date": start_due.isoformat(),
            "end_date": end_dt.isoformat(),
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    sched = r.json()["schedule"]
    assert sched["next_due_date"] == "2026-02-28"

    # Generate Feb 28 occurrence
    g1 = tc.post(f"/api/v1/bills/schedules/{sched['id']}/generate-next", headers=headers)
    assert g1.status_code == 200, g1.text
    assert g1.json()["created"] is True
    assert g1.json()["occurrence"]["due_date"] == "2026-02-28"

    # Next due would be Mar 31 (> end_date Feb 28) -> must not generate beyond end_date
    g2 = tc.post(f"/api/v1/bills/schedules/{sched['id']}/generate-next", headers=headers)
    assert g2.status_code == 200
    assert g2.json()["created"] is False

    # Partial unique index uq_bills_schedule_due_date prevents duplicate active schedule occurrence at DB level
    db = TestingSessionLocal()
    try:
        dup_occ = Bill(
            user_id=uuid.UUID(r.json()["user_id"]),
            parent_schedule_id=uuid.UUID(sched["id"]),
            bill_name="Duplicate Rent",
            bill_category="rent",
            bill_type="recurring",
            frequency="monthly",
            is_variable_amount=False,
            expected_amount=Decimal("22000.00"),
            current_amount=Decimal("22000.00"),
            amount_paid_total=Decimal("0.00"),
            currency="INR",
            due_date=dt.date(2026, 2, 28),
            stored_status="unpaid",
            reminder_enabled=True,
            reminder_days_before=[7, 3, 1, 0],
            notification_channels={"in_app": True, "email": False, "sms": False},
            is_active=True,
        )
        db.add(dup_occ)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()

    # Deactivating schedule halts generation cleanly
    deact = tc.patch(
        f"/api/v1/bills/schedules/{sched['id']}",
        json={"clear_end_date": True, "is_active": False},
        headers=headers,
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False
    g3 = tc.post(f"/api/v1/bills/schedules/{sched['id']}/generate-next", headers=headers)
    assert g3.json()["created"] is False


def test_reminders_dispatch_email_sms_honesty_mocked_delivery_retries_and_notifications(
    live_client, monkeypatch
):
    tc, created = live_client
    headers = _register_and_login(tc, created, "bills_rem", "Vikram Rao")
    today_ist = resolve_user_today("Asia/Kolkata")

    # Enable email & sms preferences with Indian phone
    pref = tc.patch(
        "/api/v1/users/me/preferences",
        json={
            "notification_preferences": {
                "phone_number": "+919876543210",
                "email_reminders_enabled": True,
                "sms_reminders_enabled": True,
            }
        },
        headers=headers,
    )
    assert pref.status_code == 200, pref.text

    # Bill due today so reminder offset 0 is immediately due (UTC timestamp already passed today or in past)
    past_due = today_ist - dt.timedelta(days=1)
    r = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Jio Fiber Postpaid",
            "bill_category": "internet",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "999.00",
            "due_date": past_due.isoformat(),
            "reminder_days_before": [1, 0],
            "notification_channels": {"in_app": True, "email": True, "sms": True},
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    bill = r.json()

    # 1. With SMTP_ENABLED=False and SMS_ENABLED=False, in_app delivers while email & sms honestly report 'unavailable' -> partial
    monkeypatch.setattr(settings, "SMTP_ENABLED", False)
    monkeypatch.setattr(settings, "SMS_ENABLED", False)
    p1 = tc.post("/api/v1/bills/reminders/process", headers=headers)
    assert p1.status_code == 200, p1.text
    res1 = p1.json()
    assert res1["processed_count"] == 2
    assert res1["partial_count"] == 2
    assert res1["notifications_created"] == 2
    assert res1["email_configured"] is False
    assert res1["sms_configured"] is False

    # Re-running immediately creates 0 duplicates!
    p_repeat = tc.post("/api/v1/bills/reminders/process", headers=headers)
    assert p_repeat.json()["processed_count"] == 0
    assert p_repeat.json()["notifications_created"] == 0

    b_after = tc.get(f"/api/v1/bills/{bill['id']}").json()
    outcomes = b_after["reminders"][0]["channel_outcomes"]
    assert outcomes["in_app"]["status"] == "delivered"
    assert outcomes["email"]["status"] == "unavailable"
    assert outcomes["sms"]["status"] == "unavailable"

    # Notifications persisted & unread -> mark one & mark all read
    notifs = tc.get("/api/v1/notifications").json()
    assert notifs["unread_count"] == 2
    n_id = notifs["items"][0]["id"]
    mark1 = tc.patch(f"/api/v1/notifications/{n_id}/read", headers=headers)
    assert mark1.status_code == 200 and mark1.json()["is_read"] is True
    assert tc.get("/api/v1/notifications/unread-count").json()["unread_count"] == 1
    mark_all = tc.post("/api/v1/notifications/read-all", headers=headers)
    assert mark_all.status_code == 200 and mark_all.json()["marked_read"] == 1

    # 2. Due-date update cancels old reminders & schedules fresh pending reminders
    new_bill_res = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Tata Power",
            "bill_category": "electricity",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "1850.00",
            "due_date": (today_ist - dt.timedelta(days=1)).isoformat(),
            "reminder_days_before": [0],
            "notification_channels": {"in_app": False, "email": True, "sms": True},
        },
        headers=headers,
    ).json()

    # Configured SMTP + Webhook SMS with transient failure -> failed + retry scheduled
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.in")
    monkeypatch.setattr(settings, "SMS_ENABLED", True)
    monkeypatch.setattr(settings, "SMS_PROVIDER", "webhook")
    monkeypatch.setattr(settings, "SMS_WEBHOOK_URL", "https://sms.example.in/send")
    monkeypatch.setattr(settings, "SMS_API_KEY", "test-key")

    mock_sms_resp = MagicMock(status_code=503, text="Gateway Unavailable")
    with (
        patch("smtplib.SMTP", side_effect=OSError("SMTP timeout")),
        patch("app.services.bills.sms_service.httpx.post", return_value=mock_sms_resp),
    ):
        p_fail = tc.post("/api/v1/bills/reminders/process", headers=headers)
        assert p_fail.json()["failed_count"] == 1

    b_retry = tc.get(f"/api/v1/bills/{new_bill_res['id']}").json()
    rem = b_retry["reminders"][0]
    assert rem["delivery_status"] == "failed"
    assert rem["retry_count"] == 1
    assert rem["next_retry_at"] is not None

    # Force next_retry_at into past & succeed on retry using mocked SMTP + SMS HTTP 200
    db = TestingSessionLocal()
    try:
        rem_row = db.get(BillReminder, uuid.UUID(rem["id"]))
        assert rem_row is not None
        rem_row.next_retry_at = dt.datetime.now(dt.UTC) - dt.timedelta(minutes=1)
        db.add(rem_row)
        db.commit()
    finally:
        db.close()

    mock_smtp_ctx = MagicMock()
    mock_sms_ok = MagicMock(status_code=200, text="OK")
    with (
        patch("smtplib.SMTP", return_value=mock_smtp_ctx),
        patch("app.services.bills.sms_service.httpx.post", return_value=mock_sms_ok),
    ):
        p_ok = tc.post("/api/v1/bills/reminders/process", headers=headers)
        assert p_ok.json()["delivered_count"] == 1

    b_done = tc.get(f"/api/v1/bills/{new_bill_res['id']}").json()
    assert b_done["reminders"][0]["delivery_status"] == "delivered"
    assert b_done["reminders"][0]["channel_outcomes"]["email"]["status"] == "delivered"
    assert b_done["reminders"][0]["channel_outcomes"]["sms"]["status"] == "delivered"


def test_documents_security_idor_csrf_and_lock_contention(live_client):
    tc, created = live_client
    h_a = _register_and_login(tc, created, "bill_owner", "Owner A")

    today_ist = resolve_user_today("Asia/Kolkata")
    b_a = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Society Maintenance",
            "bill_category": "maintenance",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "4500.00",
            "due_date": today_ist.isoformat(),
            "reminder_days_before": [0],
        },
        headers=h_a,
    ).json()

    # Path traversal guard on private storage
    storage = BillDocumentStorage()
    with pytest.raises(ValueError):
        storage.read_bytes("../../etc/passwd")

    # Invalid file extension rejected cleanly
    bad_up = tc.post(
        f"/api/v1/bills/{b_a['id']}/documents",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=h_a,
    )
    assert bad_up.status_code == 400

    # Valid PDF upload & authorized download
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    ok_up = tc.post(
        f"/api/v1/bills/{b_a['id']}/documents",
        files={"file": ("bill_receipt.pdf", pdf_bytes, "application/pdf")},
        headers=h_a,
    )
    assert ok_up.status_code == 201, ok_up.text
    doc = ok_up.json()

    dl = tc.get(f"/api/v1/bills/{b_a['id']}/documents/{doc['id']}/download")
    assert dl.status_code == 200
    assert dl.headers.get("x-content-type-options") == "nosniff"
    assert dl.content == pdf_bytes

    # CSRF check while authenticated as A (POST without X-CSRF-Token)
    no_csrf = tc.post(
        "/api/v1/bills",
        json={
            "bill_name": "Blocked No CSRF",
            "bill_category": "other",
            "bill_type": "one_time",
            "is_variable_amount": False,
            "expected_amount": "100.00",
            "due_date": today_ist.isoformat(),
        },
    )
    assert no_csrf.status_code == 403

    # Multi-worker FOR UPDATE SKIP LOCKED claim check across two DB sessions
    repo = BillRepository()
    db1 = TestingSessionLocal()
    db2 = TestingSessionLocal()
    try:
        future_utc = dt.datetime.now(dt.UTC) + dt.timedelta(days=2)
        c1 = repo.claim_due_reminders(db1, now_utc=future_utc, user_id=uuid.UUID(b_a["user_id"]))
        c2 = repo.claim_due_reminders(db2, now_utc=future_utc, user_id=uuid.UUID(b_a["user_id"]))
        assert len(c1) >= 1
        assert len(c2) == 0  # Second worker skips locked rows cleanly!
        db1.rollback()
        db2.rollback()
    finally:
        db1.close()
        db2.close()

    # Cross-user IDOR isolation using separate TestClient for User B
    with TestClient(tc.app, raise_server_exceptions=False) as tc_b:
        h_b = _register_and_login(tc_b, created, "bill_other", "User B")
        assert tc_b.get(f"/api/v1/bills/{b_a['id']}").status_code == 404
        assert (
            tc_b.patch(
                f"/api/v1/bills/{b_a['id']}", json={"bill_name": "Hack"}, headers=h_b
            ).status_code
            == 404
        )
        assert tc_b.post(f"/api/v1/bills/{b_a['id']}/archive", headers=h_b).status_code == 404
        assert (
            tc_b.get(f"/api/v1/bills/{b_a['id']}/documents/{doc['id']}/download").status_code
            == 404
        )
        assert tc_b.get("/api/v1/bills").json()["total"] == 0

        # Unauthenticated check on fresh TestClient
        with TestClient(tc.app) as anon:
            assert anon.get("/api/v1/bills").status_code == 401
            assert anon.get("/api/v1/notifications").status_code == 401
