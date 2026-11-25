import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.services.bills.recurrence import advance_due_date

TWO_DP = Decimal("0.01")


def q2(val: Decimal) -> Decimal:
    return val.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def _periods_per_year(frequency: str) -> Decimal:
    if frequency == "weekly":
        return Decimal("52")
    if frequency == "quarterly":
        return Decimal("4")
    return Decimal("12")


@dataclass
class InstallmentProjection:
    installment_number: int
    due_date: dt.date
    opening_principal: Decimal
    emi_amount: Decimal
    principal_component: Decimal
    interest_component: Decimal
    closing_principal: Decimal
    is_final_adjustment: bool = False


def calculate_emi_summary(
    principal: Decimal,
    annual_interest_rate: Decimal,
    tenure_installments: int,
    emi_frequency: str = "monthly",
    calculation_method: str = "reducing_balance",
) -> tuple[Decimal, Decimal, Decimal, list[str]]:
    """
    Deterministic Decimal EMI calculation supporting:
    - reducing_balance: EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    - flat_rate: uniform periodic principal + flat periodic interest
    - zero_interest (or rate == 0): P / n with zero interest
    """
    p = Decimal(principal)
    rate_annual = Decimal(annual_interest_rate)
    n = int(tenure_installments)
    ppy = _periods_per_year(emi_frequency)

    assumptions = [
        "Currency: INR with HALF_UP rounding to ₹0.01",
        f"Frequency: {emi_frequency} ({int(ppy)} periods/year), Tenure: {n} installment(s)",
    ]

    if n <= 0:
        raise ValueError("Tenure installments must be >= 1.")

    if calculation_method == "zero_interest" or rate_annual == Decimal("0.000"):
        emi = q2(p / Decimal(n))
        assumptions.append("Method: Zero-interest repayment (Principal / Tenure).")
        return emi, Decimal("0.00"), q2(p), assumptions

    if calculation_method == "flat_rate":
        years = Decimal(n) / ppy
        total_int = q2(p * (rate_annual / Decimal("100")) * years)
        total_rep = q2(p + total_int)
        emi = q2(total_rep / Decimal(n))
        assumptions.append(
            f"Method: Flat interest rate at {rate_annual}% p.a. on initial principal."
        )
        return emi, total_int, total_rep, assumptions

    # Standard reducing balance
    with localcontext() as ctx:
        ctx.prec = 28
        r = rate_annual / Decimal("100") / ppy
        one_plus_r_n = (Decimal("1") + r) ** n
        raw_emi = p * r * one_plus_r_n / (one_plus_r_n - Decimal("1"))
        emi = q2(raw_emi)

    schedule = generate_amortization_schedule(
        opening_principal=p,
        annual_interest_rate=rate_annual,
        periods=n,
        first_due_date=dt.date(2026, 1, 1),
        anchor_day=1,
        emi_amount=emi,
        emi_frequency=emi_frequency,
        calculation_method="reducing_balance",
    )
    total_int = q2(sum((row.interest_component for row in schedule), Decimal("0.00")))
    total_rep = q2(sum((row.emi_amount for row in schedule), Decimal("0.00")))
    assumptions.append(
        f"Method: Reducing-balance at {rate_annual}% p.a. (periodic rate {(rate_annual / ppy):.4f}%). Final installment adjusts rounding residual."
    )
    return emi, total_int, total_rep, assumptions


def generate_amortization_schedule(
    opening_principal: Decimal,
    annual_interest_rate: Decimal,
    periods: int,
    first_due_date: dt.date,
    anchor_day: int,
    emi_amount: Decimal | None = None,
    emi_frequency: str = "monthly",
    calculation_method: str = "reducing_balance",
    start_installment_number: int = 1,
    max_cap_periods: int = 600,
) -> list[InstallmentProjection]:
    """
    Generates an exact, non-negative amortization schedule preserving anchor_day
    across month-end and leap-year dates and reconciling final principal to 0.00.
    """
    bal = q2(Decimal(opening_principal))
    if bal <= Decimal("0.00") or periods <= 0:
        return []

    rate_annual = Decimal(annual_interest_rate)
    ppy = _periods_per_year(emi_frequency)

    if emi_amount is None:
        calc_emi, _, _, _ = calculate_emi_summary(
            bal, rate_annual, periods, emi_frequency, calculation_method
        )
        base_emi = calc_emi
    else:
        base_emi = q2(Decimal(emi_amount))

    schedule: list[InstallmentProjection] = []
    cur_date = first_due_date
    inst_num = start_installment_number

    flat_periodic_interest = (
        q2((bal * (rate_annual / Decimal("100"))) / ppy)
        if calculation_method == "flat_rate" and rate_annual > Decimal("0.000")
        else Decimal("0.00")
    )

    for idx in range(min(periods, max_cap_periods)):
        if bal <= Decimal("0.00"):
            break

        if calculation_method == "zero_interest" or rate_annual == Decimal("0.000"):
            interest = Decimal("0.00")
        elif calculation_method == "flat_rate":
            interest = flat_periodic_interest
        else:
            with localcontext() as ctx:
                ctx.prec = 28
                r = rate_annual / Decimal("100") / ppy
                interest = q2(bal * r)

        is_last = idx == periods - 1
        if is_last:
            principal_comp = bal
            total_inst = q2(principal_comp + interest)
            closing = Decimal("0.00")
            final_adj = total_inst != base_emi
        else:
            # Ensure even custom EMI covers principal reduction when possible without negative closing
            principal_comp = q2(base_emi - interest)
            if principal_comp <= Decimal("0.00"):
                principal_comp = Decimal("0.00")
            if principal_comp >= bal:
                principal_comp = bal
                total_inst = q2(principal_comp + interest)
                closing = Decimal("0.00")
                final_adj = total_inst != base_emi
            else:
                total_inst = base_emi
                closing = q2(bal - principal_comp)
                final_adj = False

        schedule.append(
            InstallmentProjection(
                installment_number=inst_num,
                due_date=cur_date,
                opening_principal=bal,
                emi_amount=total_inst,
                principal_component=principal_comp,
                interest_component=interest,
                closing_principal=closing,
                is_final_adjustment=final_adj,
            )
        )
        bal = closing
        inst_num += 1
        cur_date = advance_due_date(cur_date, emi_frequency, anchor_day=anchor_day)

    return schedule


def solve_remaining_periods_for_emi(
    principal: Decimal,
    annual_interest_rate: Decimal,
    emi: Decimal,
    emi_frequency: str = "monthly",
    calculation_method: str = "reducing_balance",
    cap: int = 600,
) -> int:
    """Computes revised remaining periods until balance clears for prepayment 'reduce_tenure'."""
    bal = q2(Decimal(principal))
    if bal <= Decimal("0.00"):
        return 0
    ppy = _periods_per_year(emi_frequency)
    rate_annual = Decimal(annual_interest_rate)
    count = 0
    while bal > Decimal("0.00") and count < cap:
        count += 1
        if calculation_method == "zero_interest" or rate_annual == Decimal("0.000"):
            interest = Decimal("0.00")
        elif calculation_method == "flat_rate":
            interest = q2((bal * (rate_annual / Decimal("100"))) / ppy)
        else:
            with localcontext() as ctx:
                ctx.prec = 28
                interest = q2(bal * (rate_annual / Decimal("100") / ppy))
        principal_comp = q2(emi - interest)
        if principal_comp <= Decimal("0.00"):
            return cap
        bal = max(Decimal("0.00"), q2(bal - principal_comp))
    return count


def simulate_prepayment_scenario(
    current_principal: Decimal,
    annual_interest_rate: Decimal,
    current_emi: Decimal,
    remaining_installments: int,
    next_due_date: dt.date,
    anchor_day: int,
    emi_frequency: str,
    calculation_method: str,
    extra_monthly_emi: Decimal,
    lump_sum_prepayment: Decimal,
    prepayment_mode: str,
    user_prepayment_fee: Decimal,
) -> dict:
    """
    Pure hypothetical prepayment simulator (never touches DB or ledger).
    """
    bal = q2(Decimal(current_principal))
    baseline_sched = generate_amortization_schedule(
        opening_principal=bal,
        annual_interest_rate=annual_interest_rate,
        periods=remaining_installments,
        first_due_date=next_due_date,
        anchor_day=anchor_day,
        emi_amount=current_emi,
        emi_frequency=emi_frequency,
        calculation_method=calculation_method,
    )
    baseline_interest = q2(
        sum((row.interest_component for row in baseline_sched), Decimal("0.00"))
    )
    baseline_payoff = baseline_sched[-1].due_date if baseline_sched else None

    lump = min(bal, q2(Decimal(lump_sum_prepayment)))
    revised_principal = q2(bal - lump)

    if revised_principal <= Decimal("0.00"):
        return {
            "current_outstanding_principal": bal,
            "baseline_emi": q2(current_emi),
            "baseline_remaining_installments": len(baseline_sched),
            "baseline_remaining_interest": baseline_interest,
            "baseline_payoff_date": baseline_payoff,
            "scenario_revised_emi": Decimal("0.00"),
            "scenario_remaining_installments": 0,
            "scenario_remaining_interest": Decimal("0.00"),
            "scenario_payoff_date": next_due_date,
            "revised_principal_after_lump_sum": Decimal("0.00"),
            "estimated_interest_saved": baseline_interest,
            "user_supplied_prepayment_fee": q2(user_prepayment_fee),
            "net_estimated_savings": q2(baseline_interest - q2(user_prepayment_fee)),
            "tenure_months_saved": len(baseline_sched),
        }

    extra = q2(Decimal(extra_monthly_emi))
    if prepayment_mode == "reduce_emi" and lump > Decimal("0.00"):
        new_base_emi, _, _, _ = calculate_emi_summary(
            revised_principal,
            annual_interest_rate,
            max(1, remaining_installments),
            emi_frequency,
            calculation_method,
        )
        scenario_emi = q2(new_base_emi + extra)
        scenario_periods = max(1, remaining_installments)
    else:
        scenario_emi = q2(current_emi + extra)
        scenario_periods = solve_remaining_periods_for_emi(
            revised_principal,
            annual_interest_rate,
            scenario_emi,
            emi_frequency,
            calculation_method,
        )

    scenario_sched = generate_amortization_schedule(
        opening_principal=revised_principal,
        annual_interest_rate=annual_interest_rate,
        periods=scenario_periods,
        first_due_date=next_due_date,
        anchor_day=anchor_day,
        emi_amount=scenario_emi,
        emi_frequency=emi_frequency,
        calculation_method=calculation_method,
    )
    scenario_interest = q2(
        sum((row.interest_component for row in scenario_sched), Decimal("0.00"))
    )
    scenario_payoff = scenario_sched[-1].due_date if scenario_sched else None
    saved = q2(max(Decimal("0.00"), baseline_interest - scenario_interest))
    fee = q2(Decimal(user_prepayment_fee))
    return {
        "current_outstanding_principal": bal,
        "baseline_emi": q2(current_emi),
        "baseline_remaining_installments": len(baseline_sched),
        "baseline_remaining_interest": baseline_interest,
        "baseline_payoff_date": baseline_payoff,
        "scenario_revised_emi": scenario_emi,
        "scenario_remaining_installments": len(scenario_sched),
        "scenario_remaining_interest": scenario_interest,
        "scenario_payoff_date": scenario_payoff,
        "revised_principal_after_lump_sum": revised_principal,
        "estimated_interest_saved": saved,
        "user_supplied_prepayment_fee": fee,
        "net_estimated_savings": q2(saved - fee),
        "tenure_months_saved": max(0, len(baseline_sched) - len(scenario_sched)),
    }
