from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import rate_limiter


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


def test_transfer_lifecycle_and_reversal(client: TestClient):
    """Tests atomic fund transfers between accounts and transfer reversals."""
    csrf_token = _register_and_login(client, "tr.user@example.in", "Pooja Reddy")

    # Account 1: Savings with 25,000
    s_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Primary Savings",
            "account_type": "savings",
            "opening_balance": "25000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    sav_id = s_res.json()["id"]

    # Account 2: Wallet with 2,000
    w_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Paytm Wallet",
            "account_type": "digital_wallet",
            "opening_balance": "2000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    wal_id = w_res.json()["id"]

    # 1. Validation: Same account rejected
    same_res = client.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": sav_id,
            "destination_account_id": sav_id,
            "amount": "1000.00",
            "transfer_date": "2026-11-15",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert same_res.status_code == 400

    # 2. Execute Transfer: 5,000 from Savings to Wallet
    tr_res = client.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": sav_id,
            "destination_account_id": wal_id,
            "amount": "5000.00",
            "transfer_date": "2026-11-15",
            "description": "Load Wallet for Travel",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert tr_res.status_code == 200
    tr_data = tr_res.json()
    assert tr_data["status"] == "completed"
    assert tr_data["source_account_name"] == "Primary Savings"
    assert tr_data["destination_account_name"] == "Paytm Wallet"
    tr_id = tr_data["id"]

    # Check Balances: Savings = 20,000, Wallet = 7,000
    sav_acc1 = client.get(f"/api/v1/finance/accounts/{sav_id}")
    wal_acc1 = client.get(f"/api/v1/finance/accounts/{wal_id}")
    assert Decimal(str(sav_acc1.json()["current_balance"])) == Decimal("20000.00")
    assert Decimal(str(wal_acc1.json()["current_balance"])) == Decimal("7000.00")

    # 3. Reverse the Transfer
    rev_res = client.post(
        f"/api/v1/finance/transfers/{tr_id}/reverse",
        json={"reason": "Accidental transfer"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert rev_res.status_code == 200
    assert rev_res.json()["status"] == "reversed"
    assert rev_res.json()["reversal_reason"] == "Accidental transfer"

    # Check Balances Restored: Savings = 25,000, Wallet = 2,000
    sav_acc2 = client.get(f"/api/v1/finance/accounts/{sav_id}")
    wal_acc2 = client.get(f"/api/v1/finance/accounts/{wal_id}")
    assert Decimal(str(sav_acc2.json()["current_balance"])) == Decimal("25000.00")
    assert Decimal(str(wal_acc2.json()["current_balance"])) == Decimal("2000.00")

    # 4. Double reversal rejected
    rev_again = client.post(
        f"/api/v1/finance/transfers/{tr_id}/reverse",
        json={"reason": "Re-reversal"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert rev_again.status_code == 400


def test_credit_card_bill_payment_transfer(client: TestClient):
    """Transfer from Savings to Credit Card acts as a bill payment, reducing card liability."""
    csrf_token = _register_and_login(client, "cc.payment@example.in", "Vikram Patel")

    # Savings account with 50,000
    s_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Kotak Savings",
            "account_type": "savings",
            "opening_balance": "50000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    sav_id = s_res.json()["id"]

    # Credit card with 15,000 opening liability
    c_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Kotak League Card",
            "account_type": "credit_card",
            "opening_balance": "15000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    card_id = c_res.json()["id"]

    # Pay 10,000 to Credit Card
    client.post(
        "/api/v1/finance/transfers",
        json={
            "source_account_id": sav_id,
            "destination_account_id": card_id,
            "amount": "10000.00",
            "transfer_date": "2026-11-20",
            "description": "Credit Card Bill Payment",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # Savings reduced to 40,000
    sav = client.get(f"/api/v1/finance/accounts/{sav_id}").json()
    assert Decimal(str(sav["current_balance"])) == Decimal("40000.00")

    # Card liability reduced to 5,000
    card = client.get(f"/api/v1/finance/accounts/{card_id}").json()
    assert Decimal(str(card["current_balance"])) == Decimal("5000.00")
