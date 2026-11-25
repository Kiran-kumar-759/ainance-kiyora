import datetime as dt
import uuid
from collections.abc import Generator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.rate_limit import rate_limiter
from app.db.session import get_db
from app.main import create_application
from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    LedgerEntry,
    LedgerJournal,
)
from app.models.forecasting import (
    FinancialForecast,
    ForecastEvaluation,
    ForecastExplanation,
    ForecastScenario,
    ForecastValue,
)
from app.models.intelligence import AiProcessingJob
from app.models.subscriptions import Subscription
from app.models.user import User
from app.services.ai.worker import ai_intelligence_worker
from tests.conftest import TestingSessionLocal


@pytest.fixture
def fc_api_client() -> Generator[tuple[TestClient, list[str]], None, None]:
    created_emails: list[str] = []
    app = create_application()

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    rate_limiter._requests.clear()

    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, created_emails

    app.dependency_overrides.clear()
    cleanup = TestingSessionLocal()
    try:
        for email in created_emails:
            user = cleanup.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user:
                cleanup.execute(delete(ForecastExplanation).where(ForecastExplanation.user_id == user.id))
                cleanup.execute(delete(ForecastValue).where(ForecastValue.user_id == user.id))
                cleanup.execute(delete(FinancialForecast).where(FinancialForecast.user_id == user.id))
                cleanup.execute(delete(ForecastScenario).where(ForecastScenario.user_id == user.id))
                cleanup.execute(delete(ForecastEvaluation).where(ForecastEvaluation.user_id == user.id))
                cleanup.execute(delete(AiProcessingJob).where(AiProcessingJob.user_id == user.id))
                cleanup.execute(delete(Subscription).where(Subscription.user_id == user.id))
                cleanup.execute(
                    delete(LedgerEntry).where(
                        LedgerEntry.journal_id.in_(
                            select(LedgerJournal.id).where(LedgerJournal.user_id == user.id)
                        )
                    )
                )
                cleanup.execute(delete(LedgerJournal).where(LedgerJournal.user_id == user.id))
                cleanup.execute(delete(FinancialTransaction).where(FinancialTransaction.user_id == user.id))
                cleanup.execute(delete(FinancialAccount).where(FinancialAccount.user_id == user.id))
                cleanup.execute(delete(FinancialCategory).where(FinancialCategory.user_id == user.id))
                cleanup.execute(delete(User).where(User.id == user.id))
        cleanup.commit()
    finally:
        cleanup.close()


def _register_and_login(tc: TestClient, created_emails: list[str], prefix: str) -> dict[str, str]:
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.in"
    created_emails.append(email)
    pw = "StrongPass#2026"
    tc.post(
        "/api/v1/auth/register",
        json={"email": email, "password": pw, "full_name": prefix, "mobile_number": "+919876543210"},
    )
    r2 = tc.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r2.status_code == 200
    csrf = r2.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"X-CSRF-Token": csrf}


def test_scenarios_backtesting_worker_security_and_endpoints(fc_api_client):
    tc, created_emails = fc_api_client
    assert tc.get("/api/v1/forecasting/overview").status_code == 401

    headers = _register_and_login(tc, created_emails, "fc_eval")
    acc = tc.post(
        "/api/v1/finance/accounts",
        json={"name": "Axis Salary", "account_type": "savings", "opening_balance": "200000.00"},
        headers=headers,
    ).json()

    cats = tc.get("/api/v1/finance/categories", headers=headers).json()
    cat_by_name = {c["name"]: c["id"] for c in cats}
    today = dt.date.today()

    # Seed 110 days of consistent monthly history so walk-forward backtest (cutoff today-30d) evaluates cleanly
    for m_days in (105, 75, 45, 15):
        tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc["id"],
                "transaction_type": "income",
                "amount": "80000.00",
                "currency": "INR",
                "description": "MONTHLY SALARY",
                "category_id": cat_by_name["Salary"],
                "transaction_date": (today - dt.timedelta(days=m_days)).isoformat(),
            },
            headers=headers,
        )
    for d in range(5, 110, 10):
        tc.post(
            "/api/v1/finance/transactions",
            json={
                "account_id": acc["id"],
                "transaction_type": "expense",
                "amount": "1500.00",
                "currency": "INR",
                "description": "GROCERY MART",
                "category_id": cat_by_name["Groceries"],
                "transaction_date": (today - dt.timedelta(days=d)).isoformat(),
            },
            headers=headers,
        )

    sub_res = tc.post(
        "/api/v1/subscriptions",
        json={
            "subscription_name": "Spotify Duo",
            "category": "music",
            "amount": "149.00",
            "billing_frequency": "monthly",
            "start_date": (today - dt.timedelta(days=20)).isoformat(),
            "next_renewal_date": (today + dt.timedelta(days=10)).isoformat(),
            "linked_account_id": acc["id"],
        },
        headers=headers,
    )
    assert sub_res.status_code in (200, 201)
    sub_id = sub_res.json()["id"]

    # CSRF check
    assert tc.post("/api/v1/forecasting/generate", json={"horizon_days": 30}).status_code == 403

    # Async queue & worker execution via shared PostgreSQL job queue
    q_res = tc.post(
        "/api/v1/forecasting/generate",
        json={"horizon_days": 30, "async_job": True},
        headers=headers,
    )
    assert q_res.status_code == 200
    assert q_res.json()["job_type"] == "forecast_generation"
    assert q_res.json()["status"] == "queued"

    processed = ai_intelligence_worker.process_pending_batch(max_jobs=2)
    assert processed == 1

    # Inspect individual endpoints + history + explanation
    hist = tc.get("/api/v1/forecasting/history", headers=headers).json()
    assert len(hist) >= 1
    fc_id = hist[0]["id"]
    assert tc.get(f"/api/v1/forecasting/{fc_id}", headers=headers).status_code == 200
    exps = tc.get(f"/api/v1/forecasting/{fc_id}/explanation", headers=headers).json()
    assert len(exps) >= 2
    for ep in ("cashflow", "expenses", "income", "categories", "balances", "commitments", "savings"):
        assert tc.get(f"/api/v1/forecasting/{ep}", headers=headers).status_code == 200

    # Non-mutating scenario simulation (cut expenses by 10%, cancel Spotify, +2000 recurring)
    scen_res = tc.post(
        "/api/v1/forecasting/scenarios",
        json={
            "name": "Cut Spend & Cancel Music",
            "horizon_days": 30,
            "income_delta_pct": "0",
            "expense_delta_pct": "-10",
            "extra_recurring_monthly_expense": "2000.00",
            "extra_loan_payment_monthly": "0",
            "cancelled_subscription_ids": [sub_id],
            "category_adjustments_pct": {"Groceries": "-10"},
            "save_scenario": True,
        },
        headers=headers,
    )
    assert scen_res.status_code == 200, scen_res.text
    sc = scen_res.json()
    assert sc["id"] is not None
    assert Decimal(str(sc["delta_summary"]["cashflow_diff"])) != Decimal("0.00")

    # Verify subscription remains untouched ("active")
    assert tc.get(f"/api/v1/subscriptions/{sub_id}", headers=headers).json()["status"] == "active"

    # Walk-forward backtesting evaluation (real MAE / RMSE / WAPE / Bias)
    ev_res = tc.get("/api/v1/forecasting/accuracy?horizon_days=30", headers=headers)
    assert ev_res.status_code == 200, ev_res.text
    ev = ev_res.json()
    assert ev["status"] == "evaluated"
    assert Decimal(str(ev["actual_expense"])) > Decimal("0.00")
    assert Decimal(str(ev["mae_expense"])) >= Decimal("0.00")
    assert ev["wape_expense_pct"] is not None
    assert len(tc.get("/api/v1/forecasting/evaluation/history", headers=headers).json()) >= 1

    # Cross-user isolation check (login User B -> active cookie is now User B)
    headers_b = _register_and_login(tc, created_emails, "fc_user_b")
    assert tc.get(f"/api/v1/forecasting/{fc_id}", headers=headers_b).status_code == 404
    assert tc.get(f"/api/v1/forecasting/scenarios/{sc['id']}", headers=headers_b).status_code == 404
    assert tc.delete(f"/api/v1/forecasting/scenarios/{sc['id']}", headers=headers_b).status_code == 404
    # Re-login User A for cleanup delete verification
    tc.post("/api/v1/auth/login", json={"email": created_emails[0], "password": "StrongPass#2026"})
    csrf_a = tc.cookies.get("pfm_csrf") or tc.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert tc.delete(
        f"/api/v1/forecasting/scenarios/{sc['id']}", headers={"X-CSRF-Token": csrf_a}
    ).status_code == 204
