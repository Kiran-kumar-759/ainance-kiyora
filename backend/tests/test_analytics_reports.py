import datetime as dt
import shutil
import uuid
from collections.abc import Generator
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransfer,
    LedgerEntry,
    LedgerJournal,
)
from app.models.imports import ImportBatch, ImportMappingProfile, ImportRow
from app.models.user import User
from app.services.imports.storage import LocalPrivateFileStorage
from tests.conftest import TestingSessionLocal

IST_TZ = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def live_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    """
    Real PostgreSQL multi-session TestClient fixture.
    Each HTTP request gets a fresh PostgreSQL SessionLocal.
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

    storage = LocalPrivateFileStorage()
    cleanup_db = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup_db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                shutil.rmtree(storage.base_dir / str(user.id), ignore_errors=True)
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
                    delete(ImportRow).where(
                        ImportRow.import_batch_id.in_(
                            select(ImportBatch.id).where(ImportBatch.user_id == user.id)
                        )
                    )
                )
                cleanup_db.execute(delete(ImportBatch).where(ImportBatch.user_id == user.id))
                cleanup_db.execute(
                    delete(ImportMappingProfile).where(ImportMappingProfile.user_id == user.id)
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
) -> dict:
    r = tc.post(
        "/api/v1/finance/accounts",
        json={
            "name": name,
            "account_type": account_type,
            "institution_name": "HDFC Bank",
            "opening_balance": opening_balance,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _create_category(
    tc: TestClient, headers: dict[str, str], name: str, category_type: str = "expense"
) -> dict:
    r = tc.post(
        "/api/v1/finance/categories",
        json={"name": name, "category_type": category_type, "color": "#2563eb"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _add_tx(
    tc: TestClient,
    headers: dict[str, str],
    account_id: str,
    tx_type: str,
    amount: str,
    description: str,
    tx_date: dt.date,
    category_id: str | None = None,
    merchant: str | None = None,
) -> dict:
    payload: dict[str, object] = {
        "account_id": account_id,
        "transaction_type": tx_type,
        "amount": amount,
        "currency": "INR",
        "description": description,
        "transaction_date": tx_date.isoformat(),
    }
    if category_id:
        payload["category_id"] = category_id
    if merchant:
        payload["merchant_payee"] = merchant
    r = tc.post("/api/v1/finance/transactions", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestAnalyticsAccountingAccuracy:
    def test_empty_state_zero_income_and_invalid_ranges(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "an_empty", "Empty User")

        # Empty dashboard
        d = tc.get("/api/v1/analytics/dashboard").json()
        assert d["is_empty_state"] is True
        assert Decimal(d["total_assets"]) == Decimal("0.00")
        assert Decimal(d["total_liabilities"]) == Decimal("0.00")
        assert Decimal(d["net_financial_position"]) == Decimal("0.00")
        assert d["savings_rate_pct"] is None
        assert d["income_vs_expense_series"] == []

        # Zero-income expense-only savings rate must be None (no div-by-zero), net savings negative
        wallet = _create_account(tc, headers, "Cash Wallet", "cash", "5000.00")
        today = dt.datetime.now(IST_TZ).date()
        _add_tx(tc, headers, wallet["id"], "expense", "1200.00", "Books", today)

        d2 = tc.get("/api/v1/analytics/dashboard?period=this_month").json()
        assert Decimal(d2["total_income"]) == Decimal("0.00")
        assert Decimal(d2["total_expenses"]) == Decimal("1200.00")
        assert Decimal(d2["net_savings"]) == Decimal("-1200.00")
        assert d2["savings_rate_pct"] is None

        # Invalid period & reversed custom date range rejected cleanly
        assert tc.get("/api/v1/analytics/dashboard?period=bogus").status_code == 400
        assert (
            tc.get(
                "/api/v1/analytics/dashboard?period=custom&start_date=2026-11-20&end_date=2026-11-01"
            ).status_code
            == 400
        )

    def test_transfers_credit_card_payments_update_and_reversals_accuracy(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "an_rules", "Accounting Rules")

        sav = _create_account(tc, headers, "HDFC Savings", "savings", "100000.00")
        wallet = _create_account(tc, headers, "PhonePe Wallet", "digital_wallet", "2000.00")
        card = _create_account(tc, headers, "Axis Credit Card", "credit_card", "5000.00")

        cat_salary = _create_category(tc, headers, "Salary Custom", "income")
        cat_food = _create_category(tc, headers, "Dining Custom", "expense")
        today = dt.datetime.now(IST_TZ).date()

        # 1. Salary income: ₹80,000 -> savings 1,80,000
        _add_tx(tc, headers, sav["id"], "income", "80000.00", "Monthly Salary", today, cat_salary["id"])

        # 2. Credit card purchase: ₹12,000 -> card liability becomes 17,000, expenses = 12,000
        _add_tx(tc, headers, card["id"], "expense", "12000.00", "Zomato Party", today, cat_food["id"])

        # 3. Transfer savings -> wallet: ₹10,000 (MUST NOT affect income or expenses)
        tr1 = tc.post(
            "/api/v1/finance/transfers",
            json={
                "source_account_id": sav["id"],
                "destination_account_id": wallet["id"],
                "amount": "10000.00",
                "transfer_date": today.isoformat(),
                "description": "Wallet topup",
            },
            headers=headers,
        )
        assert tr1.status_code == 200, tr1.text

        # 4. Credit card bill payment transfer savings -> card: ₹7,000 (reduces card liability to 10,000; MUST NOT count as extra expense!)
        tr2 = tc.post(
            "/api/v1/finance/transfers",
            json={
                "source_account_id": sav["id"],
                "destination_account_id": card["id"],
                "amount": "7000.00",
                "transfer_date": today.isoformat(),
                "description": "Axis Card Bill Payment",
            },
            headers=headers,
        )
        assert tr2.status_code == 200, tr2.text

        # 5. Reversed transfer savings -> wallet: ₹3,000 (reversed, must not leak anywhere)
        tr3 = tc.post(
            "/api/v1/finance/transfers",
            json={
                "source_account_id": sav["id"],
                "destination_account_id": wallet["id"],
                "amount": "3000.00",
                "transfer_date": today.isoformat(),
                "description": "Accidental transfer",
            },
            headers=headers,
        ).json()
        rev = tc.post(
            f"/api/v1/finance/transfers/{tr3['id']}/reverse",
            json={"reason": "Mistake"},
            headers=headers,
        )
        assert rev.status_code == 200

        # 6. Transaction update (creates reversed old journal + active new journal -> updated amount MUST be used)
        updatable = _add_tx(tc, headers, sav["id"], "expense", "1000.00", "Internet Bill", today, cat_food["id"])
        upd = tc.patch(
            f"/api/v1/finance/transactions/{updatable['id']}",
            json={"amount": "1500.00", "description": "Fiber Internet Updated"},
            headers=headers,
        )
        assert upd.status_code == 200

        # 7. Transaction deletion (must vanish from totals)
        to_del = _add_tx(tc, headers, sav["id"], "expense", "999.00", "Mistake Coffee", today, cat_food["id"])
        assert tc.delete(f"/api/v1/finance/transactions/{to_del['id']}", headers=headers).status_code == 204

        dash = tc.get("/api/v1/analytics/dashboard?period=this_month").json()
        # Savings: 100k + 80k - 10k - 7k - 1.5k = 161,500; Wallet: 2k + 10k = 12k -> Total Assets = 173,500
        # Credit card liability: 5k + 12k - 7k = 10,000 -> Net Financial Position = 163,500
        assert Decimal(dash["total_assets"]) == Decimal("173500.00")
        assert Decimal(dash["total_liabilities"]) == Decimal("10000.00")
        assert Decimal(dash["net_financial_position"]) == Decimal("163500.00")
        assert Decimal(dash["total_income"]) == Decimal("80000.00")
        # Expenses = 12,000 + 1,500 = 13,500 (transfers, card bill payment, deleted tx excluded!)
        assert Decimal(dash["total_expenses"]) == Decimal("13500.00")
        assert Decimal(dash["net_savings"]) == Decimal("66500.00")
        assert dash["traceability"]["excluded_transfer_count"] >= 4
        assert dash["traceability"]["excluded_reversed_count"] >= 1

    def test_uncommitted_imports_excluded_and_committed_imports_included(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "an_imp", "Import Analytics")
        sav = _create_account(tc, headers, "SBI Bank", "savings", "50000.00")
        today = dt.datetime.now(IST_TZ).date()
        d_str = today.strftime("%d/%m/%Y")

        csv_data = (
            f"Date,Description,Amount\n"
            f"{d_str},Freelance Payout,25000.00\n"
            f"{d_str},Electricity Bill,-2500.00\n"
        ).encode()

        up = tc.post(
            "/api/v1/imports/upload",
            data={"account_id": sav["id"]},
            files={"file": ("nov.csv", csv_data, "text/csv")},
            headers=headers,
        )
        assert up.status_code == 201
        batch_id = up.json()["batch"]["id"]

        tc.put(
            f"/api/v1/imports/{batch_id}/mapping",
            json={
                "date_column": "Date",
                "description_column": "Description",
                "amount_mode": "single",
                "amount_column": "Amount",
                "date_format": "DD/MM/YYYY",
                "default_currency": "INR",
            },
            headers=headers,
        )

        # Before commit: MUST NOT appear in analytics
        before = tc.get("/api/v1/analytics/dashboard?period=this_month").json()
        assert Decimal(before["total_income"]) == Decimal("0.00")
        assert Decimal(before["total_expenses"]) == Decimal("0.00")

        # After commit: MUST appear in analytics & source distribution
        assert tc.post(f"/api/v1/imports/{batch_id}/commit", headers=headers).status_code == 200

        after_exp = tc.get("/api/v1/analytics/expenses?period=this_month").json()
        after_inc = tc.get("/api/v1/analytics/income?period=this_month").json()
        assert Decimal(after_inc["total_income"]) == Decimal("25000.00")
        assert Decimal(after_exp["total_expenses"]) == Decimal("2500.00")
        assert any(s["source"] == "csv_import" for s in after_exp["by_source"])


class TestPeriodsComparisonsTrendsAndAccounts:
    def test_period_presets_comparisons_partial_warning_and_balance_history(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "an_comp", "Comparison User")
        sav = _create_account(tc, headers, "ICICI Bank", "savings", "200000.00")
        cat_groceries = _create_category(tc, headers, "Groceries Test", "expense")

        today = dt.datetime.now(IST_TZ).date()
        first_this_month = today.replace(day=1)
        prev_month_day = first_this_month - dt.timedelta(days=10)

        # Previous month expenses: ₹20,000; Current month expenses: ₹25,000 -> +25.00%
        _add_tx(tc, headers, sav["id"], "expense", "20000.00", "Oct Groceries", prev_month_day, cat_groceries["id"])
        _add_tx(tc, headers, sav["id"], "expense", "25000.00", "Nov Groceries", today, cat_groceries["id"])

        comp = tc.get("/api/v1/analytics/comparisons?comparison_preset=month_over_month").json()
        assert Decimal(comp["expenses"]["previous_value"]) == Decimal("20000.00")
        assert Decimal(comp["expenses"]["current_value"]) == Decimal("25000.00")
        assert Decimal(comp["expenses"]["absolute_difference"]) == Decimal("5000.00")
        assert Decimal(comp["expenses"]["percentage_change"]) == Decimal("25.00")
        assert comp["expenses"]["trend_direction"] == "up"
        assert comp["income"]["is_zero_baseline"] is True
        assert comp["income"]["percentage_change"] is None

        # Verify custom comparison window, weekly/quarterly/yearly cashflow, trends, and account deep dive
        assert tc.get(
            f"/api/v1/analytics/comparisons?comparison_preset=custom&start_date={first_this_month}&end_date={today}"
        ).status_code == 200

        for p in ("this_week", "this_month", "last_month", "last_3_months", "last_6_months", "this_quarter", "last_quarter", "this_year", "last_year", "all_time"):
            assert tc.get(f"/api/v1/analytics/cashflow?period={p}").status_code == 200

        trends = tc.get("/api/v1/analytics/trends?period=last_6_months&granularity=monthly").json()
        assert trends["balance_history_available"] is True
        assert len(trends["balance_history"]) >= 1

        acc_list = tc.get("/api/v1/analytics/accounts?period=last_3_months").json()
        assert len(acc_list["accounts"]) == 1
        assert Decimal(acc_list["accounts"][0]["period_expenses"]) == Decimal("45000.00")

        acc_detail = tc.get(f"/api/v1/analytics/accounts/{sav['id']}?period=last_3_months").json()
        assert acc_detail["account"]["account_id"] == sav["id"]
        assert len(acc_detail["category_distribution"]) == 1


class TestReportsCsvSecurityAndPerformance:
    def test_all_reports_filters_csv_formula_injection_and_isolation(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers_a = _register_and_login(tc, created, "rep_usera", "Report User A")
        sav_a = _create_account(tc, headers_a, "Bank A", "savings", "100000.00")
        cat_a = _create_category(tc, headers_a, "Category A", "expense")
        today = dt.datetime.now(IST_TZ).date()

        # Deliberate formula-injection description starting with '='
        _add_tx(
            tc,
            headers_a,
            sav_a["id"],
            "expense",
            "1500.50",
            "=cmd|'/C calc'!A0",
            today,
            cat_a["id"],
            merchant="+EVIL_MERCHANT()",
        )
        _add_tx(tc, headers_a, sav_a["id"], "income", "50000.00", "Consulting", today)

        # List report definitions & fetch every single report endpoint
        defs = tc.get("/api/v1/reports").json()
        assert len(defs["reports"]) == 8

        for path in (
            "/api/v1/reports/summary",
            "/api/v1/reports/income",
            "/api/v1/reports/expenses",
            "/api/v1/reports/categories",
            "/api/v1/reports/accounts",
            "/api/v1/reports/cashflow",
            "/api/v1/reports/savings",
            "/api/v1/reports/transactions",
        ):
            res = tc.get(f"{path}?period=this_month")
            assert res.status_code == 200, path

        # CSV export verification: DD/MM/YYYY date + INR decimal + formula injection escaped with leading '
        csv_res = tc.get(
            f"/api/v1/reports/export/csv?report_type=expense_report&period=this_month&account_id={sav_a['id']}"
        )
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        body = csv_res.text
        assert today.strftime("%d/%m/%Y") in body
        assert "1500.50" in body
        assert "'=cmd|'/C calc'!A0" in body
        assert "'+EVIL_MERCHANT()" in body
        assert "Consulting" not in body  # Respects expense_report filter!

        # Switch to User B: strict multi-tenant isolation & unauthorized checks
        _register_and_login(tc, created, "rep_userb", "Report User B")
        assert tc.get(f"/api/v1/analytics/accounts/{sav_a['id']}").status_code == 404
        assert tc.get(f"/api/v1/reports/summary?account_id={sav_a['id']}").status_code == 404
        assert tc.get(f"/api/v1/reports/export/csv?account_id={sav_a['id']}").status_code == 404
        b_dash = tc.get("/api/v1/analytics/dashboard").json()
        assert Decimal(b_dash["total_assets"]) == Decimal("0.00")
        assert Decimal(b_dash["total_income"]) == Decimal("0.00")

        # Logout and verify unauthenticated access blocked cleanly
        tc.cookies.clear()
        assert tc.get("/api/v1/analytics/dashboard").status_code == 401
        assert tc.get("/api/v1/reports/export/csv").status_code == 401

    def test_large_dataset_sql_aggregation_performance(
        self, live_client: tuple[TestClient, list[str]]
    ) -> None:
        tc, created = live_client
        headers = _register_and_login(tc, created, "an_perf", "Perf Tester")
        sav = _create_account(tc, headers, "Perf Bank", "savings", "500000.00")

        # Insert 200 transactions directly via DB session cleanly & verify API speed + precision
        user_email = created[-1]
        db = TestingSessionLocal()
        try:
            user = db.execute(select(User).where(User.email == user_email)).scalar_one()
            base_date = dt.datetime.now(IST_TZ).date()
            bulk_rows = [
                FinancialTransaction(
                    user_id=user.id,
                    account_id=uuid.UUID(sav["id"]),
                    transaction_type="expense",
                    amount=Decimal("125.00"),
                    currency="INR",
                    description=f"Perf Tx {i}",
                    transaction_date=base_date - dt.timedelta(days=i % 45),
                    source="manual",
                )
                for i in range(200)
            ]
            db.add_all(bulk_rows)
            db.commit()
        finally:
            db.close()

        import time

        t0 = time.monotonic()
        res = tc.get("/api/v1/analytics/expenses?period=last_3_months")
        elapsed = time.monotonic() - t0
        assert res.status_code == 200
        assert res.json()["transaction_count"] == 200
        assert Decimal(res.json()["total_expenses"]) == Decimal("25000.00")
        assert elapsed < 3.0
