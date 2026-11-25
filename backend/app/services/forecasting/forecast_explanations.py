import uuid

from app.models.finance import FinancialTransaction
from app.models.forecasting import ForecastExplanation
from app.models.intelligence import SpendingAnomaly
from app.schemas.forecasting import (
    CashflowForecastResponse,
    CategoryForecastItem,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    IncomeForecastResponse,
    RiskWarningItem,
)


def build_forecast_explanations(
    *,
    forecast_id: uuid.UUID,
    user_id: uuid.UUID,
    expenses: list[FinancialTransaction],
    incomes: list[FinancialTransaction],
    expense_fc: ExpenseForecastResponse,
    income_fc: IncomeForecastResponse,
    cashflow: CashflowForecastResponse,
    categories: list[CategoryForecastItem],
    commitments: list[CommitmentForecastItem],
    risks: list[RiskWarningItem],
    recent_anomalies: list[SpendingAnomaly],
) -> list[ForecastExplanation]:
    """
    Create deterministic, evidence-backed ForecastExplanation rows citing real transaction,
    bill, subscription, loan, category, and Phase 8 anomaly references.
    """
    rows: list[ForecastExplanation] = []

    # 1. Expense baseline explanation
    recent_exp_ids = [str(t.id) for t in expenses[-5:]]
    rows.append(
        ForecastExplanation(
            forecast_id=forecast_id,
            user_id=user_id,
            explanation_type="expense_baseline",
            title="How your expected expenses were calculated",
            narrative=expense_fc.explanation,
            confidence_label=expense_fc.confidence_label,
            supporting_refs={"transaction_ids": recent_exp_ids, "method": expense_fc.method},
        )
    )

    # 2. Income explanation
    recent_inc_ids = [str(t.id) for t in incomes[-4:]]
    rows.append(
        ForecastExplanation(
            forecast_id=forecast_id,
            user_id=user_id,
            explanation_type="income_baseline",
            title="Income regularity assessment",
            narrative=income_fc.explanation,
            confidence_label=income_fc.confidence_label,
            supporting_refs={"transaction_ids": recent_inc_ids, "income_pattern": income_fc.income_pattern},
        )
    )

    # 3. Top growing category explanation
    rising_cats = [
        c
        for c in categories
        if c.data_sufficient
        and c.expected_change_pct is not None
        and c.expected_change_pct > 5
    ]
    if rising_cats:
        top_c = sorted(rising_cats, key=lambda c: c.expected_change_pct or 0, reverse=True)[0]
        rows.append(
            ForecastExplanation(
                forecast_id=forecast_id,
                user_id=user_id,
                explanation_type="category_driver",
                title=f"{top_c.category_name} shows upward momentum",
                narrative=(
                    f"Your predicted '{top_c.category_name}' spending is {top_c.expected_change_pct}% "
                    f"above your historical monthly average (INR {top_c.historical_monthly_avg:,.2f}/mo)."
                ),
                confidence_label=top_c.confidence_label,
                supporting_refs={"category_name": top_c.category_name, "category_id": top_c.category_id},
            )
        )

    # 4. Scheduled commitment driver
    confirmed_comm = [c for c in commitments if c.commitment_status == "confirmed"]
    if confirmed_comm:
        rows.append(
            ForecastExplanation(
                forecast_id=forecast_id,
                user_id=user_id,
                explanation_type="commitments",
                title=f"{len(confirmed_comm)} confirmed obligation(s) factored into cash flow",
                narrative=(
                    f"Known bills, subscription renewals, and loan EMIs total INR "
                    f"{cashflow.known_commitments_total:,.2f} over the next {cashflow.horizon_days} days."
                ),
                confidence_label="high",
                supporting_refs={
                    "commitments": [
                        {"source_type": c.source_type, "source_id": c.source_id, "name": c.name}
                        for c in confirmed_comm[:8]
                    ]
                },
            )
        )

    # 5. Risk warning explanation
    if risks:
        r0 = risks[0]
        rows.append(
            ForecastExplanation(
                forecast_id=forecast_id,
                user_id=user_id,
                explanation_type="risk_signal",
                title=r0.title,
                narrative=r0.description,
                confidence_label=r0.confidence_label,
                supporting_refs={"contributing_records": r0.contributing_records},
            )
        )

    # 6. Phase 8 anomaly context (explicitly NOT projected forward automatically)
    if recent_anomalies:
        a0 = recent_anomalies[0]
        rows.append(
            ForecastExplanation(
                forecast_id=forecast_id,
                user_id=user_id,
                explanation_type="anomaly_context",
                title=f"Historical spike excluded as recurring obligation ({a0.category_name or 'Spending'})",
                narrative=(
                    f"Your recent Phase 8 anomaly (INR {a0.observed_amount:,.2f} vs baseline INR "
                    f"{a0.baseline_amount:,.2f}) was noted for context without automatically treating it "
                    "as a confirmed recurring future expense."
                ),
                confidence_label="medium",
                supporting_refs={"anomaly_ids": [str(a.id) for a in recent_anomalies[:3]]},
            )
        )

    return rows
