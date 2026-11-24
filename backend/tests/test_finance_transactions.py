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


def test_transactions_crud_and_balance_synchronization(client: TestClient):
    """Tests income and expense creation, balance synchronization, and safe deletion."""
    csrf_token = _register_and_login(client, "tx.crud@example.in", "Kiran Varma")

    # 1. Create a Savings Account with 10,000 opening balance
    acc_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "SBI Savings",
            "account_type": "savings",
            "opening_balance": "10000.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    acc_id = acc_res.json()["id"]

    # 2. List categories (system defaults seeded)
    cat_res = client.get("/api/v1/finance/categories")
    assert cat_res.status_code == 200
    categories = cat_res.json()
    assert len(categories) >= 15
    salary_cat = next(c for c in categories if c["name"] == "Salary")
    groceries_cat = next(c for c in categories if c["name"] == "Groceries")

    # 3. Add Income: Salary +50,000
    inc_res = client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": acc_id,
            "transaction_type": "income",
            "amount": "50000.00",
            "category_id": salary_cat["id"],
            "description": "Monthly Salary",
            "merchant_payee": "Employer Ltd",
            "transaction_date": "2026-11-01",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert inc_res.status_code == 200
    inc_data = inc_res.json()
    assert inc_data["amount"] == "50000.00"
    assert inc_data["account_name"] == "SBI Savings"
    assert inc_data["category_name"] == "Salary"

    # Verify updated account balance: 10,000 + 50,000 = 60,000
    acc_check1 = client.get(f"/api/v1/finance/accounts/{acc_id}")
    assert Decimal(str(acc_check1.json()["current_balance"])) == Decimal("60000.00")

    # 4. Add Expense: Groceries -3,500.50
    exp_res = client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": acc_id,
            "transaction_type": "expense",
            "amount": "3500.50",
            "category_id": groceries_cat["id"],
            "description": "Weekly Veggies & Provisions",
            "merchant_payee": "Blinkit",
            "transaction_date": "2026-11-05",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert exp_res.status_code == 200
    exp_id = exp_res.json()["id"]

    # Verify updated account balance: 60,000 - 3,500.50 = 56,499.50
    acc_check2 = client.get(f"/api/v1/finance/accounts/{acc_id}")
    assert Decimal(str(acc_check2.json()["current_balance"])) == Decimal("56499.50")

    # 5. Search and Filter Transactions
    filter_res = client.get("/api/v1/finance/transactions?search=Blinkit")
    assert filter_res.status_code == 200
    items = filter_res.json()["items"]
    assert len(items) == 1
    assert items[0]["description"] == "Weekly Veggies & Provisions"

    # 6. Update Expense Amount from 3,500.50 to 4,000.00
    update_res = client.patch(
        f"/api/v1/finance/transactions/{exp_id}",
        json={"amount": "4000.00", "description": "Weekly Veggies Updated"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert update_res.status_code == 200
    assert Decimal(str(update_res.json()["amount"])) == Decimal("4000.00")

    # Verify balance adjusted: 60,000 - 4,000 = 56,000.00
    acc_check3 = client.get(f"/api/v1/finance/accounts/{acc_id}")
    assert Decimal(str(acc_check3.json()["current_balance"])) == Decimal("56000.00")

    # 7. Delete Expense Transaction
    del_res = client.delete(
        f"/api/v1/finance/transactions/{exp_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert del_res.status_code == 204

    # Verify balance restored: 56,000 + 4,000 = 60,000.00
    acc_check4 = client.get(f"/api/v1/finance/accounts/{acc_id}")
    assert Decimal(str(acc_check4.json()["current_balance"])) == Decimal("60000.00")


def test_credit_card_transaction_mechanics(client: TestClient):
    """Credit card expenses increase outstanding liability; refunds/credits decrease it."""
    csrf_token = _register_and_login(client, "cc.mechanics@example.in", "Deepak Nair")

    # Create credit card with 0 starting liability
    cc_res = client.post(
        "/api/v1/finance/accounts",
        json={
            "name": "Axis Ace Card",
            "account_type": "credit_card",
            "opening_balance": "0.00",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    cc_id = cc_res.json()["id"]

    # Charge card: Expense 2,499.00
    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": cc_id,
            "transaction_type": "expense",
            "amount": "2499.00",
            "description": "Zomato Dinner",
            "transaction_date": "2026-11-10",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # Liability increases to 2,499.00
    cc_acc1 = client.get(f"/api/v1/finance/accounts/{cc_id}")
    assert Decimal(str(cc_acc1.json()["current_balance"])) == Decimal("2499.00")

    # Merchant Refund: Income 499.00
    client.post(
        "/api/v1/finance/transactions",
        json={
            "account_id": cc_id,
            "transaction_type": "income",
            "amount": "499.00",
            "description": "Zomato Dish Refund",
            "transaction_date": "2026-11-11",
        },
        headers={"X-CSRF-Token": csrf_token},
    )

    # Liability decreases to 2,000.00
    cc_acc2 = client.get(f"/api/v1/finance/accounts/{cc_id}")
    assert Decimal(str(cc_acc2.json()["current_balance"])) == Decimal("2000.00")
