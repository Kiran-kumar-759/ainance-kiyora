import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.forecasting import (
    AccountBalanceForecastItem,
    CashflowForecastResponse,
    CategoryForecastItem,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    ForecastScenarioOutcome,
    ForecastScenarioRequest,
    IncomeForecastResponse,
    RiskWarningItem,
    SavingsForecastResponse,
)


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def detect_financial_risks(
    *,
    cashflow: CashflowForecastResponse,
    income: IncomeForecastResponse,
    expenses: ExpenseForecastResponse,
    categories: list[CategoryForecastItem],
    commitments: list[CommitmentForecastItem],
    balances: list[AccountBalanceForecastItem],
    low_balance_threshold: Decimal = Decimal("5000.00"),
) -> list[RiskWarningItem]:
    """
    Identify transparent, non-judgmental cash-flow & balance pressure warnings
    grounded in projected trajectories and scheduled commitments.
    """
    risks: list[RiskWarningItem] = []

    # 1. Account low-balance projection warning
    for bal in balances:
        if bal.is_liability or bal.min_projected_balance is None:
            continue
        if bal.min_projected_balance < low_balance_threshold:
            min_pt = min(
                (p for p in bal.points if p.is_prediction),
                key=lambda p: p.projected_balance,
                default=None,
            )
            sev = "high" if bal.min_projected_balance <= Decimal("0.00") else "medium"
            risks.append(
                RiskWarningItem(
                    risk_type="low_balance",
                    severity=sev,
                    title=f"Projected low balance on {bal.account_name}",
                    description=(
                        f"{bal.account_name} may dip to INR {bal.min_projected_balance:,.2f} "
                        f"(below INR {low_balance_threshold:,.2f} threshold) under current spending and commitments."
                    ),
                    target_date=min_pt.target_date if min_pt else None,
                    projected_impact_amount=bal.min_projected_balance,
                    confidence_label=bal.confidence_label,
                    contributing_records=[{"type": "account", "id": bal.account_id, "name": bal.account_name}],
                )
            )

    # 2. Expected expenses exceeding expected income
    if (
        cashflow.expected_income is not None
        and cashflow.expected_expense is not None
        and cashflow.expected_expense > cashflow.expected_income
    ):
        deficit = _q2(cashflow.expected_expense - cashflow.expected_income)
        risks.append(
            RiskWarningItem(
                risk_type="negative_cashflow",
                severity="high" if deficit > Decimal("10000.00") else "medium",
                title=f"Projected expenses exceed income over {cashflow.horizon_days} days",
                description=(
                    f"Projected outflows (INR {cashflow.expected_expense:,.2f}) exceed estimated inflows "
                    f"(INR {cashflow.expected_income:,.2f}) by INR {deficit:,.2f}."
                ),
                projected_impact_amount=deficit,
                confidence_label=cashflow.confidence_label,
                contributing_records=[],
            )
        )

    # 3. Tight 7-day commitment concentration window
    confirmed = sorted(
        [
            c
            for c in commitments
            if c.commitment_status == "confirmed" and c.expected_amount is not None
        ],
        key=lambda c: c.due_date,
    )
    if confirmed and cashflow.expected_opening_balance > Decimal("0.00"):
        for idx, start_c in enumerate(confirmed):
            win_end = start_c.due_date + dt.timedelta(days=7)
            window_items = [
                c for c in confirmed[idx:] if c.due_date <= win_end
            ]
            win_sum = _q2(sum((Decimal(c.expected_amount) for c in window_items), Decimal("0.00")))
            if len(window_items) >= 2 and win_sum >= cashflow.expected_opening_balance * Decimal("0.45"):
                risks.append(
                    RiskWarningItem(
                        risk_type="commitment_cluster",
                        severity="medium",
                        title=f"{len(window_items)} commitments due within 7 days of {start_c.due_date}",
                        description=(
                            f"Scheduled obligations totaling INR {win_sum:,.2f} fall between "
                            f"{start_c.due_date} and {win_end}, representing a concentrated cash outflow."
                        ),
                        target_date=start_c.due_date,
                        projected_impact_amount=win_sum,
                        confidence_label=cashflow.confidence_label,
                        contributing_records=[
                            {"type": c.source_type, "id": c.source_id, "name": c.name}
                            for c in window_items[:5]
                        ],
                    )
                )
                break

    # 4. Unusual projected category growth
    for cat in categories:
        if (
            cat.data_sufficient
            and cat.expected_change_pct is not None
            and cat.expected_change_pct >= Decimal("25.00")
            and cat.predicted_amount is not None
            and cat.predicted_amount >= Decimal("2000.00")
        ):
            risks.append(
                RiskWarningItem(
                    risk_type="category_surge",
                    severity="low",
                    title=f"Rising trend in {cat.category_name} (+{cat.expected_change_pct}%)",
                    description=cat.explanation,
                    projected_impact_amount=cat.predicted_amount,
                    confidence_label=cat.confidence_label,
                    contributing_records=[
                        {
                            "type": "category",
                            "id": cat.category_id or cat.category_name,
                            "name": cat.category_name,
                        }
                    ],
                )
            )
            break

    return risks


def compute_savings_projection(
    *,
    income: IncomeForecastResponse,
    expenses: ExpenseForecastResponse,
    cashflow: CashflowForecastResponse,
    horizon_days: int,
) -> SavingsForecastResponse:
    """
    Estimate projected savings margins clearly framed as estimates rather than guaranteed deposits.
    """
    hist_savings = None
    if income.historical_monthly_avg is not None and expenses.historical_monthly_avg is not None:
        hist_savings = _q2(income.historical_monthly_avg - expenses.historical_monthly_avg)

    if cashflow.expected_income is None or cashflow.expected_expense is None:
        return SavingsForecastResponse(
            horizon_days=horizon_days,
            confidence_label="insufficient_data",
            historical_monthly_savings=hist_savings,
            disclaimer=(
                "Insufficient verified income or expense history to project net savings. "
                "Projections are informational estimates only and never execute account transfers."
            ),
        )

    horizon_savings = _q2(cashflow.expected_income - cashflow.expected_expense)
    scale_to_month = Decimal("30") / Decimal(str(max(1, horizon_days)))
    monthly_savings = _q2(horizon_savings * scale_to_month)
    monthly_income_proj = _q2(cashflow.expected_income * scale_to_month)
    rate_pct = (
        _q2((monthly_savings / monthly_income_proj) * Decimal("100"))
        if monthly_income_proj > Decimal("0.00")
        else Decimal("0.00")
    )

    yearly_savings = (
        _q2(monthly_savings * Decimal("12"))
        if income.confidence_label in ("high", "medium")
        else None
    )

    conservative_inc = (income.lower_bound or cashflow.expected_income) * scale_to_month
    conservative_exp = (expenses.upper_bound or cashflow.expected_expense) * scale_to_month
    best_inc = (income.upper_bound or cashflow.expected_income) * scale_to_month
    best_exp = (expenses.lower_bound or cashflow.expected_expense) * scale_to_month

    return SavingsForecastResponse(
        horizon_days=horizon_days,
        confidence_label=income.confidence_label
        if income.confidence_score <= expenses.confidence_score
        else expenses.confidence_label,
        historical_monthly_savings=hist_savings,
        expected_monthly_savings=monthly_savings,
        expected_savings_rate_pct=rate_pct,
        projected_horizon_savings=horizon_savings,
        projected_yearly_savings=yearly_savings,
        conservative_monthly_savings=_q2(conservative_inc - conservative_exp),
        best_case_monthly_savings=_q2(best_inc - best_exp),
        disclaimer=(
            "Projected savings reflect estimated net cash flow (income minus expenses) and do not "
            "automatically deposit funds into savings accounts or assume investment returns."
        ),
    )


def evaluate_what_if_scenario(
    *,
    req: ForecastScenarioRequest,
    baseline_cashflow: CashflowForecastResponse,
    categories: list[CategoryForecastItem],
    cancelled_subscription_savings: Decimal,
) -> tuple[ForecastScenarioOutcome, ForecastScenarioOutcome, dict[str, Decimal]]:
    """
    Pure side-effect-free hypothetical scenario calculator comparing baseline vs modified trajectory.
    """
    base_inc = baseline_cashflow.expected_income or Decimal("0.00")
    base_exp = baseline_cashflow.expected_expense or Decimal("0.00")
    base_comm = baseline_cashflow.known_commitments_total or Decimal("0.00")
    base_net = _q2(base_inc - base_exp)
    base_close = _q2(baseline_cashflow.expected_opening_balance + base_net)

    baseline = ForecastScenarioOutcome(
        expected_income=_q2(base_inc),
        expected_expense=_q2(base_exp),
        known_commitments=_q2(base_comm),
        net_cashflow=base_net,
        projected_savings=_q2(max(Decimal("0.00"), base_net)),
        projected_closing_balance=base_close,
    )

    horizon_factor = Decimal(str(req.horizon_days)) / Decimal("30")
    scen_inc = _q2(base_inc * (Decimal("1.00") + (req.income_delta_pct / Decimal("100"))))

    # Apply overall expense % change + optional category-specific adjustments cleanly
    scen_exp = _q2(base_exp * (Decimal("1.00") + (req.expense_delta_pct / Decimal("100"))))
    if req.category_adjustments_pct:
        cat_lookup = {c.category_name.lower(): c for c in categories if c.predicted_amount is not None}
        for cat_name, adj_pct in req.category_adjustments_pct.items():
            matched = cat_lookup.get(cat_name.strip().lower())
            if matched and matched.predicted_amount is not None:
                scen_exp += _q2(matched.predicted_amount * (adj_pct / Decimal("100")))

    extra_recur = _q2(req.extra_recurring_monthly_expense * horizon_factor)
    extra_loan = _q2(req.extra_loan_payment_monthly * horizon_factor)
    scen_comm = _q2(max(Decimal("0.00"), base_comm - cancelled_subscription_savings + extra_recur + extra_loan))
    scen_exp = _q2(max(Decimal("0.00"), scen_exp - cancelled_subscription_savings + extra_recur + extra_loan))
    scen_net = _q2(scen_inc - scen_exp)
    scen_close = _q2(baseline_cashflow.expected_opening_balance + scen_net)

    scenario = ForecastScenarioOutcome(
        expected_income=scen_inc,
        expected_expense=scen_exp,
        known_commitments=scen_comm,
        net_cashflow=scen_net,
        projected_savings=_q2(max(Decimal("0.00"), scen_net)),
        projected_closing_balance=scen_close,
    )

    delta = {
        "income_diff": _q2(scenario.expected_income - baseline.expected_income),
        "expense_diff": _q2(scenario.expected_expense - baseline.expected_expense),
        "cashflow_diff": _q2(scenario.net_cashflow - baseline.net_cashflow),
        "savings_diff": _q2(scenario.projected_savings - baseline.projected_savings),
        "closing_balance_diff": _q2(
            scenario.projected_closing_balance - baseline.projected_closing_balance
        ),
    }
    return baseline, scenario, delta
