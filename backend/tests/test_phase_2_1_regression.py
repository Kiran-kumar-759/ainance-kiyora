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
from app.models.finance import (
    BankingConnection,
    FinancialAccount,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.user import User
from tests.conftest import TestingSessionLocal


@pytest.fixture
def live_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    """
    TestClient that mirrors production get_db(): every HTTP request receives a fresh,
    independent PostgreSQL SessionLocal (no shared uncommitted test transaction).
    Guarantees that missing db.commit() bugs are immediately caught.
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

    # Clean up committed test data from pfm_test
    cleanup_db = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                # Delete child ledger entries & transactions first due to RESTRICT FKs
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
                    delete(FinancialAccount).where(FinancialAccount.user_id == user.id)
                )
                cleanup_db.delete(user)
        cleanup_db.commit()
    finally:
        cleanup_db.close()


def _register_and_login_live(
    tc: TestClient, created_emails: list[str], prefix: str, name: str
) -> tuple[str, str]:
    rate_limiter.clear()
    email = f"{prefix}.{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)

    reg = tc.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "StrongPassword123!"},
    )
    assert reg.status_code == 201

    login = tc.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login.status_code == 200
    csrf_token = login.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf_token is not None
    return email, csrf_token


def test_real_multi_session_account_creation_all_types(live_client):
    """
    Bug A regression test: verifies manual account creation across all 6 account types
    persists across independent PostgreSQL sessions, creates balanced ledger entries,
    and rejects invalid/duplicate/unauthenticated/missing-CSRF inputs.
    """
    tc, created_emails = live_client
    _, csrf = _register_and_login_live(tc, created_emails, "phase21.acc", "Ananya Iyer")

    # 1. Invalid inputs rejected cleanly
    blank_name = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "   ", "account_type": "savings", "opening_balance": "100.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert blank_name.status_code == 422

    neg_bal = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "Negative", "account_type": "savings", "opening_balance": "-10.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert neg_bal.status_code == 422

    # Missing CSRF rejected
    no_csrf = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "No CSRF", "account_type": "savings", "opening_balance": "100.00"},
    )
    assert no_csrf.status_code == 403

    # 2. Create all 6 supported account types
    test_accounts = [
        ("SBI Savings", "savings", "SBI", "••4821", "25000.00"),
        ("HDFC Current", "current", "HDFC Bank", "••9901", "10000.50"),
        ("Home Cash", "cash", None, None, "1500.25"),
        ("Axis Magnus Card", "credit_card", "Axis Bank", "••3344", "5000.00"),
        ("PhonePe Wallet", "digital_wallet", "PhonePe", "••7788", "2500.75"),
        ("Emergency Stash", "other", "Treasury", None, "0.00"),
    ]

    created_ids = []
    for name, acc_type, inst, ident, ob in test_accounts:
        res = tc.post(
            "/api/v1/finance/accounts",
            json={
                "name": name,
                "account_type": acc_type,
                "institution_name": inst,
                "account_identifier": ident,
                "currency": "INR",
                "opening_balance": ob,
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert res.status_code == 200, f"Failed for {acc_type}: {res.text}"
        body = res.json()
        assert Decimal(str(body["current_balance"])) == Decimal(ob)
        assert body["source"] == "manual"
        created_ids.append(body["id"])

    # 3. Duplicate active manual account returns HTTP 409
    dup = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": "sbi savings",
            "account_type": "savings",
            "opening_balance": "100.00",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert dup.status_code == 409
    assert "already exists" in dup.json()["detail"]

    # 4. Separate GET request (new PostgreSQL session!) confirms real commit
    list_res = tc.get("/api/v1/finance/accounts")
    assert list_res.status_code == 200
    listed = list_res.json()
    assert len(listed) == 6
    assert {a["name"] for a in listed} == {item[0] for item in test_accounts}

    # 5. Verify balanced ledger entries directly in a fresh PostgreSQL session
    verify_db = TestingSessionLocal()
    try:
        for acc_id_str in created_ids:
            acc_uuid = uuid.UUID(acc_id_str)
            acc_row = verify_db.get(FinancialAccount, acc_uuid)
            assert acc_row is not None
            if acc_row.opening_balance > Decimal("0.00"):
                journals = list(
                    verify_db.execute(
                        select(LedgerJournal).where(
                            LedgerJournal.reference == f"OB-{acc_uuid.hex[:8]}"
                        )
                    ).scalars()
                )
                assert len(journals) == 1
                entries = list(
                    verify_db.execute(
                        select(LedgerEntry).where(LedgerEntry.journal_id == journals[0].id)
                    ).scalars()
                )
                debits = sum(e.amount for e in entries if e.entry_type == "debit")
                credits = sum(e.amount for e in entries if e.entry_type == "credit")
                assert debits == credits == acc_row.opening_balance
    finally:
        verify_db.close()

    # 6. Expired/unauthenticated session check (new client without cookies)
    unauth_client = TestClient(tc.app, raise_server_exceptions=False)
    unauth_res = unauth_client.get("/api/v1/finance/accounts")
    assert unauth_res.status_code == 401


def test_partial_failure_rolls_back_atomically(live_client):
    """
    Verifies that if an exception occurs mid-operation (either during manual account
    opening-balance posting or during multi-account demo import), PostgreSQL rolls back
    completely with zero orphan accounts or partial records.
    """
    tc, created_emails = live_client
    email, csrf = _register_and_login_live(tc, created_emails, "phase21.rollback", "Rollback Test")

    # 1. Simulate failure inside LedgerService during manual account creation
    with patch(
        "app.services.finance.ledger_service.LedgerService.post_opening_balance",
        side_effect=RuntimeError("Simulated ledger failure"),
    ):
        fail_res = tc.post(
            "/api/v1/finance/accounts",
            json={
                "name": "Should Rollback",
                "account_type": "savings",
                "opening_balance": "5000.00",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert fail_res.status_code == 500

    # Must leave 0 accounts in PostgreSQL
    assert tc.get("/api/v1/finance/accounts").json() == []

    # 2. Connect demo bank, then fail on the 2nd account during multi-account import
    conn_res = tc.post(
        "/api/v1/banking/connections/demo",
        json={"provider_id": "demo_national_bank", "consent_given": True},
        headers={"X-CSRF-Token": csrf},
    )
    assert conn_res.status_code == 200
    conn_id = conn_res.json()["id"]

    call_count = 0
    from app.services.finance.ledger_service import LedgerService

    orig_post_ob = LedgerService.post_opening_balance

    def fail_on_second(self_ls, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated mid-import failure on account #2")
        return orig_post_ob(self_ls, *args, **kwargs)

    with patch.object(LedgerService, "post_opening_balance", autospec=True, side_effect=fail_on_second):
        import_fail = tc.post(
            f"/api/v1/banking/connections/{conn_id}/accounts/import",
            json={"account_ids": ["dnb_sav_001", "dnb_cur_002"]},
            headers={"X-CSRF-Token": csrf},
        )
        assert import_fail.status_code == 500

    # Verify BOTH dnb_sav_001 and dnb_cur_002 rolled back completely!
    assert tc.get("/api/v1/finance/accounts").json() == []

    verify_db = TestingSessionLocal()
    try:
        user = verify_db.execute(select(User).where(User.email == email)).scalar_one()
        journals = list(
            verify_db.execute(
                select(LedgerJournal).where(LedgerJournal.user_id == user.id)
            ).scalars()
        )
        assert journals == []
    finally:
        verify_db.close()


def test_real_multi_session_demo_banking_workflow(live_client):
    """
    Bug B regression test: verifies the full simulated banking workflow across
    independent PostgreSQL sessions: provider listing, consent, connect, discover,
    selective import, idempotent re-import, sync, idempotent re-sync, sync history,
    disconnect, and cross-user isolation.
    """
    tc, created_emails = live_client
    _, csrf_a = _register_and_login_live(tc, created_emails, "phase21.banka", "Bank User A")

    # 1. Provider discovery (all 3 simulated Indian providers)
    providers = tc.get("/api/v1/banking/providers").json()
    assert len(providers) == 3
    assert {p["provider_id"] for p in providers} == {
        "demo_national_bank",
        "demo_private_bank",
        "demo_digital_bank",
    }

    # 2. Connect Demo National Bank
    conn_res = tc.post(
        "/api/v1/banking/connections/demo",
        json={"provider_id": "demo_national_bank", "consent_given": True},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert conn_res.status_code == 200
    conn_id = conn_res.json()["id"]

    # Fresh GET confirms persisted in PostgreSQL
    conns = tc.get("/api/v1/banking/connections").json()
    assert len(conns) == 1
    assert conns[0]["id"] == conn_id
    assert conns[0]["status"] == "connected"

    # 3. Discover accounts
    discovered = tc.get(f"/api/v1/banking/connections/{conn_id}/accounts").json()
    assert len(discovered) == 2

    # Unknown account ID rejected cleanly
    bad_import = tc.post(
        f"/api/v1/banking/connections/{conn_id}/accounts/import",
        json={"account_ids": ["nonexistent_ext_id"]},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert bad_import.status_code == 400

    # 4. Import dnb_sav_001 (even if duplicated in request payload)
    imp_res = tc.post(
        f"/api/v1/banking/connections/{conn_id}/accounts/import",
        json={"account_ids": ["dnb_sav_001", "dnb_sav_001"]},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert imp_res.status_code == 200
    imported = imp_res.json()
    assert len(imported) == 1
    assert imported[0]["source"] == "demo_bank"
    assert Decimal(str(imported[0]["current_balance"])) == Decimal("125450.00")
    imported_acc_id = imported[0]["id"]

    # Duplicate import call is idempotent (creates 0 duplicates)
    dup_imp = tc.post(
        f"/api/v1/banking/connections/{conn_id}/accounts/import",
        json={"account_ids": ["dnb_sav_001"]},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert dup_imp.status_code == 200
    assert dup_imp.json() == []

    # Account appears in Financial Accounts across fresh session
    accounts_list = tc.get("/api/v1/finance/accounts").json()
    assert len(accounts_list) == 1
    assert accounts_list[0]["source"] == "demo_bank"

    # 5. Sync transactions & check balance recalculation
    sync1 = tc.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert sync1.status_code == 200
    assert sync1.json()["accounts_synced"] == 1
    assert sync1.json()["transactions_synced"] == 4

    # Balance: 125450 + 85000 - 18500 - 3200 - 4650 = 184100.00
    acc_after_sync = tc.get(f"/api/v1/finance/accounts/{imported_acc_id}").json()
    assert Decimal(str(acc_after_sync["current_balance"])) == Decimal("184100.00")

    # 6. Second sync creates 0 duplicates
    sync2 = tc.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert sync2.status_code == 200
    assert sync2.json()["transactions_synced"] == 0

    tx_res = tc.get("/api/v1/finance/transactions?source=demo_bank")
    assert tx_res.status_code == 200
    assert tx_res.json()["total"] == 4

    # Sync history endpoint records both runs
    runs = tc.get(f"/api/v1/banking/connections/{conn_id}/sync-runs").json()
    assert len(runs) == 2
    assert runs[0]["transactions_synced"] == 0
    assert runs[1]["transactions_synced"] == 4

    # 7. Disconnect preserves history and blocks future sync
    disc = tc.post(
        f"/api/v1/banking/connections/{conn_id}/disconnect",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert disc.status_code == 200
    assert disc.json()["status"] == "disconnected"
    assert disc.json()["connected_accounts_count"] == 1

    sync_blocked = tc.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_a},
    )
    assert sync_blocked.status_code == 400
    assert len(tc.get("/api/v1/finance/accounts").json()) == 1
    assert tc.get("/api/v1/finance/transactions?source=demo_bank").json()["total"] == 4

    # 8. Cross-user isolation: User B cannot touch User A's accounts or connection
    tc_b = TestClient(tc.app, raise_server_exceptions=False)
    _, csrf_b = _register_and_login_live(tc_b, created_emails, "phase21.bankb", "Bank User B")

    assert tc_b.get("/api/v1/banking/connections").json() == []
    assert tc_b.get(f"/api/v1/banking/connections/{conn_id}").status_code == 404
    assert tc_b.get(f"/api/v1/banking/connections/{conn_id}/accounts").status_code == 404
    assert tc_b.get(f"/api/v1/banking/connections/{conn_id}/sync-runs").status_code == 404
    assert (
        tc_b.post(
            f"/api/v1/banking/connections/{conn_id}/accounts/import",
            json={"account_ids": ["dnb_cur_002"]},
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )
    assert (
        tc_b.post(
            f"/api/v1/banking/connections/{conn_id}/sync",
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )
    assert (
        tc_b.post(
            f"/api/v1/banking/connections/{conn_id}/disconnect",
            headers={"X-CSRF-Token": csrf_b},
        ).status_code
        == 404
    )
    assert tc_b.get(f"/api/v1/finance/accounts/{imported_acc_id}").status_code == 404

    # Verify BankingConnection row count is still 1 for User A in PostgreSQL
    verify_db = TestingSessionLocal()
    try:
        conn_row = verify_db.get(BankingConnection, uuid.UUID(conn_id))
        assert conn_row is not None
        assert conn_row.status == "disconnected"
    finally:
        verify_db.close()


def test_negative_balance_prevention_across_transactions_and_transfers(live_client):
    """
    Verifies that asset account balances (savings, current, cash, wallet, other)
    cannot go negative through expenses, transaction edits, income deletions,
    fund transfers, transfer reversals, or opening balance reductions.
    """
    tc, created_emails = live_client
    _, csrf = _register_and_login_live(tc, created_emails, "phase21.noneg", "No Negative Balance")

    # Create Savings with ₹10,000 and Wallet with ₹0
    sav_res = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "SBI Guard Savings", "account_type": "savings", "opening_balance": "10000.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert sav_res.status_code == 200
    sav_id = sav_res.json()["id"]

    wal_res = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "UPI Guard Wallet", "account_type": "digital_wallet", "opening_balance": "0.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert wal_res.status_code == 200
    wal_id = wal_res.json()["id"]

    # 1. Expense > available balance is rejected cleanly with HTTP 400
    over_exp = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": sav_id,
            "transaction_type": "expense",
            "amount": "50000.00",
            "description": "Movie Theatre Overdraft Attempt",
            "transaction_date": "2026-11-25",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert over_exp.status_code == 400
    assert "Insufficient balance" in over_exp.json()["detail"]
    assert Decimal(str(tc.get(f"/api/v1/finance/accounts/{sav_id}").json()["current_balance"])) == Decimal("10000.00")

    # 2. Valid expense ₹6,000 leaves ₹4,000
    ok_exp = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": sav_id,
            "transaction_type": "expense",
            "amount": "6000.00",
            "description": "Groceries",
            "transaction_date": "2026-11-25",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert ok_exp.status_code == 200
    exp_id = ok_exp.json()["id"]

    # 3. Updating expense from ₹6,000 to ₹15,000 (would leave -₹5,000) is rejected & rolled back
    over_patch = tc.patch(
        f"/api/v1/finance/transactions/{exp_id}",
        json={"amount": "15000.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert over_patch.status_code == 400
    assert "Insufficient balance" in over_patch.json()["detail"]
    assert Decimal(str(tc.get(f"/api/v1/finance/accounts/{sav_id}").json()["current_balance"])) == Decimal("4000.00")

    # 4. Reducing opening balance below net expenses (e.g. ₹2,000 < ₹6,000 spent) is rejected
    over_ob = tc.patch(
        f"/api/v1/finance/accounts/{sav_id}/opening-balance",
        json={"opening_balance": "2000.00"},
        headers={"X-CSRF-Token": csrf},
    )
    assert over_ob.status_code == 400
    assert Decimal(str(tc.get(f"/api/v1/finance/accounts/{sav_id}").json()["current_balance"])) == Decimal("4000.00")

    # 5. Transfer > available balance (₹5,000 > ₹4,000) is rejected
    over_tr = tc.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": sav_id,
            "destination_account_id": wal_id,
            "amount": "5000.00",
            "transfer_date": "2026-11-25",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert over_tr.status_code == 400
    assert "Insufficient balance" in over_tr.json()["detail"]

    # 6. Income + transfer + delete income check: add ₹3,000 to Wallet, spend ₹2,000, deleting ₹3,000 income blocked
    inc_res = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": wal_id,
            "transaction_type": "income",
            "amount": "3000.00",
            "description": "Cashback",
            "transaction_date": "2026-11-25",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert inc_res.status_code == 200
    wal_inc_id = inc_res.json()["id"]

    wal_exp = tc.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": wal_id,
            "transaction_type": "expense",
            "amount": "2000.00",
            "description": "Wallet Spend",
            "transaction_date": "2026-11-25",
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert wal_exp.status_code == 200

    del_inc = tc.delete(
        f"/api/v1/finance/transactions/{wal_inc_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert del_inc.status_code == 400
    assert "negative" in del_inc.json()["detail"]
    assert Decimal(str(tc.get(f"/api/v1/finance/accounts/{wal_id}").json()["current_balance"])) == Decimal("1000.00")

