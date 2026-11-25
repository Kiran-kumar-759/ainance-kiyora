import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.assistant import EvidenceItem
from app.services.ai.intelligence_service import IntelligenceService
from app.services.bills.status_engine import resolve_user_today
from app.services.forecasting.commitment_forecaster import collect_upcoming_commitments
from app.services.forecasting.forecast_service import ForecastService

LIABILITY_ACCOUNT_TYPES = {"credit_card", "loan_liability"}


def _ev_id(prefix: str, idx: int) -> str:
    return f"{prefix}_{idx}"


def tool_get_account_balances(
    db: Session, user: User
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    repo = ForecastRepository()
    accounts = repo.list_active_accounts(db, user.id)
    liquid_total = Decimal("0.00")
    liability_total = Decimal("0.00")
    rows: list[dict[str, Any]] = []
    evidence: list[EvidenceItem] = []

    for idx, acc in enumerate(accounts, start=1):
        bal = Decimal(acc.current_balance or Decimal("0.00"))
        is_liab = acc.account_type in LIABILITY_ACCOUNT_TYPES
        if is_liab:
            liability_total += bal
        else:
            liquid_total += bal
        rows.append(
            {
                "account_id": str(acc.id),
                "name": acc.name,
                "account_type": acc.account_type,
                "is_liability": is_liab,
                "current_balance_inr": str(bal),
            }
        )
        evidence.append(
            EvidenceItem(
                evidence_id=_ev_id("acc", idx),
                origin="personal_financial_record",
                title=f"Account Balance: {acc.name}",
                summary=f"Current verified {'liability' if is_liab else 'balance'}: INR {bal:,.2f} ({acc.account_type}).",
                source_reference=f"account:{acc.id}",
                is_confirmed_source=True,
            )
        )

    return (
        {
            "account_count": len(rows),
            "liquid_balance_inr": str(liquid_total),
            "liability_balance_inr": str(liability_total),
            "net_position_inr": str(liquid_total - liability_total),
            "accounts": rows,
        },
        evidence,
    )


def tool_get_spending_summary(
    db: Session,
    user: User,
    *,
    days: int = 30,
    category_query: str | None = None,
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    fc_repo = ForecastRepository()
    intel_repo = IntelligenceRepository()
    tz = fc_repo.get_user_timezone(db, user.id)
    today = resolve_user_today(tz)
    safe_days = min(max(7, days), 365)
    start_date = today - dt.timedelta(days=safe_days)

    txs = intel_repo.list_eligible_transactions(
        db, user.id, date_from=start_date, date_to=today, include_transfers=False
    )
    expenses = [t for t in txs if t.transaction_type == "expense"]
    incomes = [t for t in txs if t.transaction_type == "income"]

    if category_query:
        q = category_query.lower()
        expenses = [
            t
            for t in expenses
            if (t.category and q in t.category.name.lower())
            or q in (t.description or "").lower()
            or q in (t.merchant_payee or "").lower()
        ]

    total_exp = sum((Decimal(t.amount) for t in expenses), Decimal("0.00"))
    total_inc = sum((Decimal(t.amount) for t in incomes), Decimal("0.00"))

    by_cat: dict[str, Decimal] = {}
    for t in expenses:
        c_name = t.category.name if t.category else "Uncategorized"
        by_cat[c_name] = by_cat.get(c_name, Decimal("0.00")) + Decimal(t.amount)

    top_cats = [
        {"category": k, "amount_inr": str(v)}
        for k, v in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:8]
    ]
    sample_txs = [
        {
            "date": t.transaction_date.isoformat(),
            "amount_inr": str(t.amount),
            "description": t.description or t.merchant_payee or "Transaction",
            "category": t.category.name if t.category else "Uncategorized",
        }
        for t in expenses[:6]
    ]

    evidence = [
        EvidenceItem(
            evidence_id="spend_calc_1",
            origin="deterministic_calculation",
            title=f"Spending Summary ({start_date} to {today})",
            summary=(
                f"Computed over {len(expenses)} non-transfer expenses totaling INR {total_exp:,.2f} "
                f"and {len(incomes)} inflows totaling INR {total_inc:,.2f} (active ledger journals)."
            ),
            source_reference=f"transactions:{start_date}:{today}",
            is_confirmed_source=True,
            meta={"top_categories": top_cats[:4]},
        )
    ]

    return (
        {
            "period_start": start_date.isoformat(),
            "period_end": today.isoformat(),
            "expense_count": len(expenses),
            "income_count": len(incomes),
            "total_expense_inr": str(total_exp),
            "total_income_inr": str(total_inc),
            "net_cashflow_inr": str(total_inc - total_exp),
            "top_categories": top_cats,
            "recent_matching_expenses": sample_txs,
        },
        evidence,
    )


def tool_get_upcoming_commitments(
    db: Session, user: User, *, horizon_days: int = 30
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    repo = ForecastRepository()
    tz = repo.get_user_timezone(db, user.id)
    as_of = resolve_user_today(tz)
    items, confirmed_total, unknown_cnt = collect_upcoming_commitments(
        db,
        repo,
        user.id,
        as_of_date=as_of,
        horizon_days=min(max(7, horizon_days), 180),
    )

    confirmed = [c for c in items if c.commitment_status == "confirmed"]
    unconfirmed = [c for c in items if c.commitment_status != "confirmed"]

    evidence: list[EvidenceItem] = [
        EvidenceItem(
            evidence_id="comm_1",
            origin="personal_financial_record",
            title=f"Upcoming Commitments (Next {horizon_days} days)",
            summary=(
                f"{len(confirmed)} confirmed bill/subscription/EMI obligations totaling INR {confirmed_total:,.2f}"
                + (
                    f" (+ {unknown_cnt} variable unknown-amount bills, {len(unconfirmed)} unconfirmed candidates)."
                    if unknown_cnt or unconfirmed
                    else "."
                )
            ),
            source_reference="commitments",
            is_confirmed_source=True,
        )
    ]

    return (
        {
            "as_of_date": as_of.isoformat(),
            "horizon_days": horizon_days,
            "confirmed_total_inr": str(confirmed_total),
            "unknown_variable_count": unknown_cnt,
            "confirmed_obligations": [
                {
                    "name": c.name,
                    "source_type": c.source_type,
                    "due_date": c.due_date.isoformat(),
                    "amount_inr": str(c.expected_amount) if c.expected_amount is not None else "Unknown (Variable)",
                    "certainty": c.amount_certainty,
                }
                for c in confirmed[:12]
            ],
            "unconfirmed_candidates": [
                {
                    "name": c.name,
                    "due_date": c.due_date.isoformat(),
                    "estimated_amount_inr": str(c.expected_amount),
                }
                for c in unconfirmed[:6]
            ],
        },
        evidence,
    )


def tool_get_forecast_and_insights(
    db: Session, user: User, *, horizon_days: int = 30
) -> tuple[dict[str, Any], list[EvidenceItem]]:
    fc_svc = ForecastService()
    intel_svc = IntelligenceService()

    ov = fc_svc.get_overview(db, user, horizon_days=min(max(7, horizon_days), 365))
    ins_list = intel_svc.list_insights(db, user)
    anom_list = intel_svc.list_anomalies(db, user, review_status="open")

    evidence: list[EvidenceItem] = [
        EvidenceItem(
            evidence_id="fc_1",
            origin="forecast_or_scenario",
            title=f"{ov.forecast.horizon_days}-Day Forecast ({ov.forecast.confidence_label})",
            summary=(
                f"Expected Income: {ov.cashflow.expected_income or 'Insufficient data'} INR; "
                f"Expected Expenses: {ov.cashflow.expected_expense or 'Insufficient data'} INR; "
                f"Projected Closing Liquid Balance: {ov.cashflow.projected_closing_balance or 'Insufficient data'} INR."
            ),
            source_reference=f"forecast:{ov.forecast.id}",
            is_confirmed_source=True,
            meta={"method": ov.forecast.method, "assumptions": ov.forecast.assumptions[:3]},
        )
    ]
    for idx, ex in enumerate(ov.explanations[:2], start=1):
        evidence.append(
            EvidenceItem(
                evidence_id=f"fc_exp_{idx}",
                origin="forecast_or_scenario",
                title=ex.title,
                summary=ex.narrative,
                source_reference=f"forecast_explanation:{ex.id}",
                is_confirmed_source=True,
            )
        )
    for idx, ins in enumerate(ins_list.items[:2], start=1):
        evidence.append(
            EvidenceItem(
                evidence_id=f"intel_ins_{idx}",
                origin="deterministic_calculation",
                title=ins.title,
                summary=ins.description,
                source_reference=f"insight:{ins.id}",
                is_confirmed_source=True,
            )
        )

    return (
        {
            "forecast_status": ov.forecast.status,
            "confidence": ov.forecast.confidence_label,
            "method": ov.forecast.method,
            "expected_income_inr": str(ov.cashflow.expected_income) if ov.cashflow.expected_income is not None else None,
            "expected_expense_inr": str(ov.cashflow.expected_expense) if ov.cashflow.expected_expense is not None else None,
            "predicted_net_cashflow_inr": str(ov.cashflow.predicted_net_cashflow) if ov.cashflow.predicted_net_cashflow is not None else None,
            "projected_closing_balance_inr": str(ov.cashflow.projected_closing_balance) if ov.cashflow.projected_closing_balance is not None else None,
            "expected_monthly_savings_inr": str(ov.savings.expected_monthly_savings) if ov.savings.expected_monthly_savings is not None else None,
            "assumptions": ov.forecast.assumptions,
            "risks": [{"title": r.title, "description": r.description, "severity": r.severity} for r in ov.risks[:4]],
            "insights": [{"title": i.title, "description": i.description} for i in ins_list.items[:4]],
            "open_anomalies": [{"category": a.category_name, "explanation": a.explanation} for a in anom_list.items[:3]],
        },
        evidence,
    )
