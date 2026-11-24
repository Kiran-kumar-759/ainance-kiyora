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


def test_account_creation_and_opening_balance(client: TestClient):
    """Verifies creating multiple account types with opening balances and exact Decimal arithmetic."""
    csrf_token = _register_and_login(client, "acc.test1@example.in", "Aarav Sharma")

    # 1. Create Savings Account
    res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "HDFC Salary Account",
            "account_type": "savings",
            "institution_name": "HDFC Bank",
            "account_identifier": "••4821",
            "currency": "INR",
            "opening_balance": "50000.50",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "HDFC Salary Account"
    assert data["account_type"] == "savings"
    assert data["currency"] == "INR"
    assert Decimal(str(data["opening_balance"])) == Decimal("50000.50")
    assert Decimal(str(data["current_balance"])) == Decimal("50000.50")
    assert data["status"] == "active"
    savings_id = data["id"]

    # 2. Create Credit Card Account (Liability)
    res_cc = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "ICICI Coral Card",
            "account_type": "credit_card",
            "institution_name": "ICICI Bank",
            "account_identifier": "••9104",
            "currency": "INR",
            "opening_balance": "12500.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_cc.status_code == 200
    data_cc = res_cc.json()
    assert data_cc["account_type"] == "credit_card"
    assert Decimal(str(data_cc["current_balance"])) == Decimal("12500.00")

    # 3. Retrieve Summary
    summary_res = client.get("/api/v1/finance/accounts/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_accounts"] == 2
    assert summary["active_accounts"] == 2
    assert Decimal(str(summary["total_assets"])) == Decimal("50000.50")
    assert Decimal(str(summary["total_credit_liabilities"])) == Decimal("12500.00")
    assert Decimal(str(summary["net_position"])) == Decimal("37500.50")

    # 4. Correct Opening Balance on Savings Account
    ob_res = client.patch(
        f"/api/v1/finance/accounts/{savings_id}/opening-balance",
        json={"opening_balance": "60000.00"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert ob_res.status_code == 200
    assert Decimal(str(ob_res.json()["current_balance"])) == Decimal("60000.00")


def test_account_archive_restore_and_cross_user_isolation(client: TestClient):
    """Verifies archiving, restoring, and strict tenant isolation across different users."""
    csrf_token_a = _register_and_login(client, "user.a@example.in", "User Alpha")

    # User A creates an account
    acc_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Alpha Cash",
            "account_type": "cash",
            "opening_balance": "5000.00",
        },
        headers={"X-CSRF-Token": csrf_token_a},
    )
    account_a_id = acc_res.json()["id"]

    # Archive account
    archive_res = client.post(
        f"/api/v1/finance/accounts/{account_a_id}/archive",
        headers={"X-CSRF-Token": csrf_token_a},
    )
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "archived"

    # Default list excludes archived
    list_active = client.get("/api/v1/finance/accounts")
    assert len(list_active.json()) == 0

    # List with include_archived=true includes it
    list_all = client.get("/api/v1/finance/accounts?include_archived=true")
    assert len(list_all.json()) == 1

    # Restore account
    restore_res = client.post(
        f"/api/v1/finance/accounts/{account_a_id}/restore",
        headers={"X-CSRF-Token": csrf_token_a},
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["status"] == "active"

    # User B registers and attempts to access User A's account
    csrf_token_b = _register_and_login(client, "user.b@example.in", "User Beta")

    # Attempt GET User A's account
    unauth_get = client.get(f"/api/v1/finance/accounts/{account_a_id}")
    assert unauth_get.status_code == 404

    # Attempt PATCH User A's account
    unauth_patch = client.patch(
        f"/api/v1/finance/accounts/{account_a_id}",
        json={"name": "Hacked Name"},
        headers={"X-CSRF-Token": csrf_token_b},
    )
    assert unauth_patch.status_code == 404

    # Attempt ARCHIVE User A's account
    unauth_archive = client.post(
        f"/api/v1/finance/accounts/{account_a_id}/archive",
        headers={"X-CSRF-Token": csrf_token_b},
    )
    assert unauth_archive.status_code == 404
