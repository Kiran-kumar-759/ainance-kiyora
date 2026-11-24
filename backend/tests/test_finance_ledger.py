from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.models.finance import LedgerEntry, LedgerJournal


def _register_and_login(client: TestClient, email: str, name: str) -> str:
    rate_limiter.clear()
    client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "SecurePassword123!"},
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    assert login_res.status_code == 200
    csrf_token = login_res.cookies.get(settings.CSRF_COOKIE_NAME)
    assert csrf_token is not None
    return csrf_token


def test_double_entry_ledger_journal_balancing(client: TestClient, db_session: Session):
    """
    Verifies that every single journal posted to the database is strictly balanced:
    sum(debit amounts) == sum(credit amounts) with zero discrepancy.
    """
    csrf_token = _register_and_login(client, "ledger.audit@example.in", "Audit Lead")

    # 1. Create Account with Opening Balance (triggers opening_balance journal)
    acc1_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Audit Savings",
            "account_type": "savings",
            "opening_balance": "45250.75",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    acc1_id = acc1_res.json()["id"]

    acc2_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Audit Current",
            "account_type": "current",
            "opening_balance": "10000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    acc2_id = acc2_res.json()["id"]

    # 2. Add Income (triggers income journal)
    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": acc1_id,
            "transaction_type": "income",
            "amount": "15000.25",
            "description": "Consulting Fee",
            "transaction_date": "2026-11-18",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # 3. Add Expense (triggers expense journal)
    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": acc1_id,
            "transaction_type": "expense",
            "amount": "3250.00",
            "description": "Software Subscription",
            "transaction_date": "2026-11-19",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # 4. Transfer between accounts (triggers transfer journal)
    client.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": acc1_id,
            "destination_account_id": acc2_id,
            "amount": "5000.00",
            "transfer_date": "2026-11-20",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # Query all journals in db_session
    journals = db_session.execute(select(LedgerJournal)).scalars().all()
    assert len(journals) >= 5

    for journal in journals:
        entries = (
            db_session.execute(select(LedgerEntry).where(LedgerEntry.journal_id == journal.id))
            .scalars()
            .all()
        )

        total_debits = sum(e.amount for e in entries if e.entry_type == "debit")
        total_credits = sum(e.amount for e in entries if e.entry_type == "credit")

        assert total_debits == total_credits, (
            f"Journal {journal.id} ({journal.journal_type}) is unbalanced: "
            f"Debits={total_debits}, Credits={total_credits}"
        )
