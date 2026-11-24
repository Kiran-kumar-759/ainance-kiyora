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


def test_financial_dashboard_metrics(client: TestClient):
    """Verifies that the financial dashboard aggregates real database balances, income, and expenses."""
    csrf_token = _register_and_login(client, "dash.metrics@example.in", "Ananya Sen")

    # 1. Empty state
    empty_res = client.get("/api/v1/finance/dashboard")
    assert empty_res.status_code == 200
    empty_data = empty_res.json()
    assert empty_data["account_count"] == 0
    assert Decimal(str(empty_data["total_assets"])) == Decimal("0.00")
    assert Decimal(str(empty_data["net_financial_position"])) == Decimal("0.00")
    assert empty_data["recent_transactions"] == []

    # 2. Add Savings Account + Credit Card
    s_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Standard Chartered Savings",
            "account_type": "savings",
            "opening_balance": "80000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    sav_id = s_res.json()["id"]

    client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Standard Chartered Ultimate Card",
            "account_type": "credit_card",
            "opening_balance": "15000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # 3. Add Income this month: 65,000
    import datetime as dt

    today = dt.date.today().isoformat()

    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": sav_id,
            "transaction_type": "income",
            "amount": "65000.00",
            "description": "Tech Consulting",
            "transaction_date": today,
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # 4. Add Expense this month: 20,000
    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": sav_id,
            "transaction_type": "expense",
            "amount": "20000.00",
            "description": "App Development Tools",
            "transaction_date": today,
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # 5. Check Dashboard
    dash_res = client.get("/api/v1/finance/dashboard?period=this_month")
    assert dash_res.status_code == 200
    dash = dash_res.json()

    assert dash["account_count"] == 2
    # Savings: 80,000 + 65,000 - 20,000 = 125,000. Liabilities: 15,000
    assert Decimal(str(dash["total_assets"])) == Decimal("125000.00")
    assert Decimal(str(dash["total_liabilities"])) == Decimal("15000.00")
    assert Decimal(str(dash["net_financial_position"])) == Decimal("110000.00")
    assert Decimal(str(dash["total_income"])) == Decimal("65000.00")
    assert Decimal(str(dash["total_expenses"])) == Decimal("20000.00")
    assert Decimal(str(dash["net_savings"])) == Decimal("45000.00")
    # Savings rate = 45000 / 65000 = 69.23%
    assert Decimal(str(dash["savings_rate_pct"])) == Decimal("69.23")
    assert len(dash["recent_transactions"]) == 2
