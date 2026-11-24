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


def test_simulated_banking_full_workflow_and_idempotency(client: TestClient):
    """
    Tests the complete simulated banking workflow:
    1. Provider discovery
    2. Consent requirement
    3. Connection initialization
    4. Account discovery and selection import
    5. Transaction sync
    6. Idempotent re-sync (0 duplicates)
    7. Disconnect workflow
    """
    csrf_token = _register_and_login(client, "banking.flow@example.in", "Rohan Mehta")

    # 1. Provider discovery
    prov_res = client.get("/api/v1/banking/providers")
    assert prov_res.status_code == 200
    providers = prov_res.json()
    assert len(providers) >= 3
    assert any(p["provider_id"] == "demo_national_bank" for p in providers)
    assert all(p["is_simulated"] is True for p in providers)

    # 2. Consent required: rejected if consent_given = False
    no_consent = client.post(
        "/api/v1/banking/connections/demo",
        json={"provider_id": "demo_national_bank", "consent_given": False},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert no_consent.status_code == 400

    # 3. Connect with consent
    conn_res = client.post(
        "/api/v1/banking/connections/demo",
        json={"provider_id": "demo_national_bank", "consent_given": True},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert conn_res.status_code == 200
    conn_data = conn_res.json()
    assert conn_data["institution_name"] == "Demo National Bank of India"
    assert conn_data["status"] == "connected"
    assert conn_data["is_simulated"] is True
    conn_id = conn_data["id"]

    # 4. Discover Accounts
    disc_res = client.get(f"/api/v1/banking/connections/{conn_id}/accounts")
    assert disc_res.status_code == 200
    discovered = disc_res.json()
    assert len(discovered) == 2
    assert discovered[0]["already_imported"] is False

    # 5. Import Selected Accounts
    import_res = client.post(
        f"/api/v1/banking/connections/{conn_id}/accounts/import",
        json={"account_ids": ["dnb_sav_001"]},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert import_res.status_code == 200
    imported = import_res.json()
    assert len(imported) == 1
    assert imported[0]["source"] == "demo_bank"
    assert imported[0]["name"] == "DNB Salary Savings Account"
    assert Decimal(str(imported[0]["opening_balance"])) == Decimal("125450.00")

    # Re-discovering now shows already_imported = True for dnb_sav_001
    disc_res2 = client.get(f"/api/v1/banking/connections/{conn_id}/accounts")
    discovered2 = disc_res2.json()
    dnb_sav = next(a for a in discovered2 if a["external_account_id"] == "dnb_sav_001")
    assert dnb_sav["already_imported"] is True

    # 6. Synchronize Transactions (First Run)
    sync_res1 = client.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert sync_res1.status_code == 200
    sync_data1 = sync_res1.json()
    assert sync_data1["status"] == "success"
    assert sync_data1["accounts_synced"] == 1
    assert sync_data1["transactions_synced"] == 4  # 4 sample transactions for dnb_sav_001

    # Verify transactions appear in transaction list
    tx_list1 = client.get("/api/v1/finance/transactions?source=demo_bank")
    assert tx_list1.status_code == 200
    assert tx_list1.json()["total"] == 4

    # 7. Synchronize Transactions (Second Run - Idempotency Check)
    sync_res2 = client.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert sync_res2.status_code == 200
    sync_data2 = sync_res2.json()
    assert sync_data2["transactions_synced"] == 0  # 0 duplicates created!

    tx_list2 = client.get("/api/v1/finance/transactions?source=demo_bank")
    assert tx_list2.json()["total"] == 4  # Still exactly 4!

    # 8. Disconnect Connection
    disc_conn = client.post(
        f"/api/v1/banking/connections/{conn_id}/disconnect",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert disc_conn.status_code == 200
    assert disc_conn.json()["status"] == "disconnected"

    # Syncing while disconnected is blocked
    sync_disc = client.post(
        f"/api/v1/banking/connections/{conn_id}/sync",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert sync_disc.status_code == 400
