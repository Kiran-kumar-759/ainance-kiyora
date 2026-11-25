import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from app.models.finance import FinancialAccount, FinancialTransaction
from app.schemas.forecasting import (
    AccountBalanceForecastItem,
    AccountBalanceProjectionPoint,
    CashflowForecastResponse,
    CashflowPeriodPoint,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    IncomeForecastResponse,
)


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


LIABILITY_ACCOUNT_TYPES = {"credit_card", "loan_liability"}


def build_cashflow_and_balances(
    *,
    accounts: list[FinancialAccount],
    expenses: list[FinancialTransaction],
    incomes: list[FinancialTransaction],
    commitments: list[CommitmentForecastItem],
    expense_fc: ExpenseForecastResponse,
    income_fc: IncomeForecastResponse,
    daily_disc_expense_rate: Decimal,
    dow_multipliers: dict[int, Decimal],
    daily_income_rate: Decimal,
    as_of_date: dt.date,
    horizon_days: int,
    timezone: str,
) -> tuple[CashflowForecastResponse, list[AccountBalanceForecastItem]]:
    """
    Project daily & monthly cashflow and account-level balances using verified balances,
    daily discretionary baseline, and confirmed scheduled obligations.
    Credit card & loan liability accounts remain negative/liability trajectories (never bank cash).
    """
    confirmed_commitments = [c for c in commitments if c.commitment_status == "confirmed"]
    confirmed_with_amt = [c for c in confirmed_commitments if c.expected_amount is not None]
    confirmed_total = _q2(sum((c.expected_amount for c in confirmed_with_amt), Decimal("0.00")))
    unknown_var_count = sum(1 for c in confirmed_commitments if c.expected_amount is None)

    liquid_accounts = [a for a in accounts if a.account_type not in LIABILITY_ACCOUNT_TYPES]
    opening_liquid_balance = _q2(
        sum((Decimal(a.current_balance or Decimal("0.00")) for a in liquid_accounts), Decimal("0.00"))
    )

    commitments_by_date: dict[dt.date, Decimal] = {}
    for c in confirmed_with_amt:
        commitments_by_date[c.due_date] = commitments_by_date.get(c.due_date, Decimal("0.00")) + Decimal(
            c.expected_amount
        )

    # Trailing 30 days historical actuals for visual distinction in cashflow chart
    daily_points: list[CashflowPeriodPoint] = []
    hist_start = as_of_date - dt.timedelta(days=min(30, horizon_days))
    hist_inc_by_day: dict[dt.date, Decimal] = {}
    hist_exp_by_day: dict[dt.date, Decimal] = {}
    for tx in incomes:
        if hist_start <= tx.transaction_date <= as_of_date:
            hist_inc_by_day[tx.transaction_date] = hist_inc_by_day.get(
                tx.transaction_date, Decimal("0.00")
            ) + Decimal(tx.amount)
    for tx in expenses:
        if hist_start <= tx.transaction_date <= as_of_date:
            hist_exp_by_day[tx.transaction_date] = hist_exp_by_day.get(
                tx.transaction_date, Decimal("0.00")
            ) + Decimal(tx.amount)

    cur_hist = hist_start
    while cur_hist <= as_of_date:
        inc_d = _q2(hist_inc_by_day.get(cur_hist, Decimal("0.00")))
        exp_d = _q2(hist_exp_by_day.get(cur_hist, Decimal("0.00")))
        if inc_d > Decimal("0.00") or exp_d > Decimal("0.00") or cur_hist == as_of_date:
            daily_points.append(
                CashflowPeriodPoint(
                    label=cur_hist.strftime("%d %b"),
                    target_date=cur_hist,
                    is_prediction=False,
                    source_kind="historical_actual",
                    income_amount=inc_d,
                    expense_amount=exp_d,
                    commitment_amount=Decimal("0.00"),
                    net_cashflow=_q2(inc_d - exp_d),
                    projected_closing_balance=opening_liquid_balance
                    if cur_hist == as_of_date
                    else None,
                )
            )
        cur_hist += dt.timedelta(days=1)

    # Forward daily projections from as_of_date + 1 to as_of_date + horizon_days
    running_balance = opening_liquid_balance
    total_pred_income = Decimal("0.00")
    total_pred_expense = Decimal("0.00")
    monthly_buckets: dict[str, dict] = {}

    for offset in range(1, horizon_days + 1):
        d = as_of_date + dt.timedelta(days=offset)
        dow_mult = dow_multipliers.get(d.weekday(), Decimal("1.00"))
        disc_exp_d = _q2(daily_disc_expense_rate * dow_mult) if expense_fc.predicted_total is not None else Decimal("0.00")
        comm_d = _q2(commitments_by_date.get(d, Decimal("0.00")))
        exp_d = _q2(disc_exp_d + comm_d)
        inc_d = _q2(daily_income_rate) if income_fc.predicted_total is not None else Decimal("0.00")

        net_d = _q2(inc_d - exp_d)
        running_balance = _q2(running_balance + net_d)
        total_pred_income += inc_d
        total_pred_expense += exp_d

        src_kind = "known_commitment" if comm_d > Decimal("0.00") else "statistical_prediction"
        if horizon_days <= 90 or offset % 3 == 0 or comm_d > Decimal("0.00") or offset == horizon_days:
            daily_points.append(
                CashflowPeriodPoint(
                    label=d.strftime("%d %b"),
                    target_date=d,
                    is_prediction=True,
                    source_kind=src_kind,
                    income_amount=inc_d,
                    expense_amount=exp_d,
                    commitment_amount=comm_d,
                    net_cashflow=net_d,
                    projected_closing_balance=running_balance,
                )
            )

        mk = d.strftime("%Y-%m")
        mb = monthly_buckets.setdefault(
            mk,
            {
                "last_date": d,
                "income": Decimal("0.00"),
                "expense": Decimal("0.00"),
                "commitment": Decimal("0.00"),
                "closing": running_balance,
            },
        )
        mb["last_date"] = d
        mb["income"] += inc_d
        mb["expense"] += exp_d
        mb["commitment"] += comm_d
        mb["closing"] = running_balance

    monthly_points = [
        CashflowPeriodPoint(
            label=mk,
            target_date=mb["last_date"],
            is_prediction=True,
            source_kind="statistical_prediction",
            income_amount=_q2(mb["income"]),
            expense_amount=_q2(mb["expense"]),
            commitment_amount=_q2(mb["commitment"]),
            net_cashflow=_q2(mb["income"] - mb["expense"]),
            projected_closing_balance=_q2(mb["closing"]),
        )
        for mk, mb in sorted(monthly_buckets.items())
    ]

    has_any_prediction = (
        expense_fc.predicted_total is not None or income_fc.predicted_total is not None
    )
    projected_net = (
        _q2(total_pred_income - total_pred_expense) if has_any_prediction else None
    )
    projected_closing = (
        _q2(opening_liquid_balance + projected_net) if projected_net is not None else None
    )

    all_dates = [t.transaction_date for t in (expenses + incomes)]
    cutoff_date = max(all_dates) if all_dates else None

    assumptions = [
        f"Opening liquid balance is INR {opening_liquid_balance:,.2f} across {len(liquid_accounts)} active liquid account(s).",
        "Internal transfers and reversed ledger entries are excluded from income/expense rates.",
    ]
    if unknown_var_count > 0:
        assumptions.append(
            f"{unknown_var_count} variable-amount commitment(s) with unknown exact INR amount remain excluded from totals rather than zero-coerced."
        )

    limitations = [
        "Forecasts estimate future cash flows and never create confirmed ledger transactions.",
    ]
    if income_fc.confidence_label == "insufficient_data":
        limitations.append("Income history is insufficient; net cash flow omits projected inflows.")
    if expense_fc.confidence_label == "insufficient_data":
        limitations.append("Expense baseline is insufficient; outflows reflect confirmed commitments only.")

    cashflow_resp = CashflowForecastResponse(
        horizon_days=horizon_days,
        as_of_date=as_of_date,
        data_cutoff_date=cutoff_date,
        timezone=timezone,
        method=expense_fc.method,
        confidence_label=expense_fc.confidence_label,
        confidence_score=expense_fc.confidence_score,
        expected_income=_q2(total_pred_income) if income_fc.predicted_total is not None else None,
        expected_expense=_q2(total_pred_expense) if has_any_prediction else None,
        known_commitments_total=confirmed_total,
        unknown_variable_commitments_count=unknown_var_count,
        predicted_net_cashflow=projected_net,
        expected_opening_balance=opening_liquid_balance,
        projected_closing_balance=projected_closing,
        daily_points=daily_points,
        monthly_points=monthly_points,
        assumptions=assumptions,
        limitations=limitations,
    )

    # Account-level balance projections
    balance_items: list[AccountBalanceForecastItem] = []
    liquid_count = max(1, len(liquid_accounts))
    unlinked_daily_net = Decimal("0.00")
    if has_any_prediction:
        # Allocate net statistical flow proportionally across liquid accounts by positive share (or evenly)
        unlinked_daily_net = (
            (_q2(daily_income_rate) if income_fc.predicted_total is not None else Decimal("0.00"))
            - (_q2(daily_disc_expense_rate) if expense_fc.predicted_total is not None else Decimal("0.00"))
        )

    for acc in accounts:
        is_liab = acc.account_type in LIABILITY_ACCOUNT_TYPES
        cur_bal = _q2(Decimal(acc.current_balance or Decimal("0.00")))
        acc_id_str = str(acc.id)

        if is_liab:
            # Liability accounts display current debt liability & explicit loan/card assumptions (never positive bank balance)
            balance_items.append(
                AccountBalanceForecastItem(
                    account_id=acc_id_str,
                    account_name=acc.name,
                    account_type=acc.account_type,
                    is_liability=True,
                    current_balance=cur_bal,
                    projected_end_balance=cur_bal,
                    min_projected_balance=cur_bal,
                    projected_change=Decimal("0.00"),
                    confidence_label=expense_fc.confidence_label,
                    assumptions=[
                        f"{acc.account_type.replace('_', ' ').title()} balance reflects liability exposure; "
                        "not included in liquid cash runway."
                    ],
                    points=[
                        AccountBalanceProjectionPoint(
                            target_date=as_of_date,
                            label="Today",
                            projected_balance=cur_bal,
                            is_prediction=False,
                        )
                    ],
                )
            )
            continue

        share = Decimal("1.00") / Decimal(str(liquid_count))
        if opening_liquid_balance > Decimal("0.00") and cur_bal > Decimal("0.00"):
            share = cur_bal / opening_liquid_balance

        acc_comm_by_date: dict[dt.date, Decimal] = {}
        for c in confirmed_with_amt:
            if c.account_id == acc_id_str:
                acc_comm_by_date[c.due_date] = acc_comm_by_date.get(
                    c.due_date, Decimal("0.00")
                ) + Decimal(c.expected_amount)
            elif c.account_id is None:
                acc_comm_by_date[c.due_date] = acc_comm_by_date.get(
                    c.due_date, Decimal("0.00")
                ) + _q2(Decimal(c.expected_amount) * share)

        run_bal = cur_bal
        min_bal = cur_bal
        pts: list[AccountBalanceProjectionPoint] = [
            AccountBalanceProjectionPoint(
                target_date=as_of_date,
                label=as_of_date.strftime("%d %b"),
                projected_balance=cur_bal,
                is_prediction=False,
            )
        ]

        step_days = max(1, horizon_days // 15) if horizon_days > 30 else 1
        for offset in range(1, horizon_days + 1):
            d = as_of_date + dt.timedelta(days=offset)
            net_step = _q2(unlinked_daily_net * share) - acc_comm_by_date.get(d, Decimal("0.00"))
            run_bal = _q2(run_bal + net_step)
            if run_bal < min_bal:
                min_bal = run_bal
            if offset % step_days == 0 or offset == horizon_days or acc_comm_by_date.get(d, Decimal("0.00")) > 0:
                pts.append(
                    AccountBalanceProjectionPoint(
                        target_date=d,
                        label=d.strftime("%d %b"),
                        projected_balance=run_bal,
                        is_prediction=True,
                    )
                )

        balance_items.append(
            AccountBalanceForecastItem(
                account_id=acc_id_str,
                account_name=acc.name,
                account_type=acc.account_type,
                is_liability=False,
                current_balance=cur_bal,
                projected_end_balance=run_bal if has_any_prediction or confirmed_with_amt else None,
                min_projected_balance=min_bal if has_any_prediction or confirmed_with_amt else None,
                projected_change=_q2(run_bal - cur_bal) if has_any_prediction or confirmed_with_amt else None,
                confidence_label=expense_fc.confidence_label,
                assumptions=[
                    f"Allocates {float(share * 100):.0f}% of unlinked cash flow plus linked commitments targeting '{acc.name}'."
                ],
                points=pts,
            )
        )

    return cashflow_resp, balance_items
