import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, stdev

from app.models.finance import FinancialTransaction
from app.models.intelligence import TransactionCategorization
from app.schemas.forecasting import (
    CategoryForecastItem,
    CommitmentForecastItem,
    ExpenseForecastResponse,
    IncomeForecastResponse,
)
from app.services.forecasting.forecast_confidence import (
    apply_confidence_bounds,
    assess_forecast_confidence,
)


def _month_key(d: dt.date) -> str:
    return d.strftime("%Y-%m")


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weighted_monthly_rate(ordered_months: list[tuple[str, Decimal]]) -> tuple[Decimal, Decimal, Decimal]:
    """
    Compute (weighted_monthly, historical_avg, dampened_trend_pct) over ordered (YYYY-MM, amount) pairs.
    """
    if not ordered_months:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")

    vals = [v for _, v in ordered_months]
    hist_avg = _q2(sum(vals, Decimal("0.00")) / Decimal(len(vals)))

    # Linearly increasing weights favoring more recent months
    weights = [Decimal(i + 1) for i in range(len(vals))]
    total_w = sum(weights)
    weighted = _q2(sum(v * w for v, w in zip(vals, weights)) / total_w)

    trend_pct = Decimal("0.00")
    if len(vals) >= 2:
        prev_avg = sum(vals[:-1], Decimal("0.00")) / Decimal(len(vals) - 1)
        latest = vals[-1]
        if prev_avg > Decimal("0.00"):
            raw_pct = ((latest - prev_avg) / prev_avg) * Decimal("100")
            # Dampen extreme jumps to [-35%, +35%] to keep forecasts realistic
            bounded = max(Decimal("-35.00"), min(Decimal("35.00"), raw_pct))
            trend_pct = _q2(bounded)
            if abs(bounded) >= Decimal("5.00") and len(vals) >= 3:
                adj_factor = Decimal("1.00") + (bounded * Decimal("0.35") / Decimal("100"))
                weighted = _q2(weighted * adj_factor)

    return weighted, hist_avg, trend_pct


def forecast_expenses(
    *,
    expenses: list[FinancialTransaction],
    commitments: list[CommitmentForecastItem],
    as_of_date: dt.date,
    horizon_days: int,
) -> tuple[ExpenseForecastResponse, Decimal, dict[int, Decimal]]:
    """
    Forecast future expenses cleanly combining statistical discretionary baseline + confirmed commitments,
    excluding scheduled commitment categories/sources from discretionary base to avoid double-counting.
    Returns (response, daily_discretionary_rate, day_of_week_multipliers).
    """
    confirmed_commitments = [
        c for c in commitments if c.commitment_status == "confirmed" and c.expected_amount is not None
    ]
    confirmed_total = sum((c.expected_amount for c in confirmed_commitments), Decimal("0.00"))

    if not expenses and not confirmed_commitments:
        return (
            ExpenseForecastResponse(
                horizon_days=horizon_days,
                method="insufficient_data",
                confidence_label="insufficient_data",
                confidence_score=Decimal("0.0000"),
                explanation="Not enough verified historical expenses or confirmed commitments to generate a reliable expense forecast.",
            ),
            Decimal("0.00"),
            {i: Decimal("1.00") for i in range(7)},
        )

    dates = [tx.transaction_date for tx in expenses]
    coverage_days = ((max(dates) - min(dates)).days + 1) if len(dates) >= 2 else (1 if dates else 0)
    if len(expenses) < 3 or (coverage_days < 14 and not confirmed_commitments):
        if confirmed_commitments:
            return (
                ExpenseForecastResponse(
                    horizon_days=horizon_days,
                    method="confirmed_commitments_only",
                    confidence_label="low",
                    confidence_score=Decimal("0.3500"),
                    predicted_total=_q2(confirmed_total),
                    lower_bound=_q2(confirmed_total),
                    upper_bound=_q2(confirmed_total * Decimal("1.20")),
                    explanation=(
                        f"Transaction history covers {coverage_days} day(s) ({len(expenses)} txn), so historical baseline is "
                        f"insufficient; projection reflects only {len(confirmed_commitments)} confirmed upcoming commitment(s)."
                    ),
                ),
                Decimal("0.00"),
                {i: Decimal("1.00") for i in range(7)},
            )
        return (
            ExpenseForecastResponse(
                horizon_days=horizon_days,
                method="insufficient_data",
                confidence_label="insufficient_data",
                confidence_score=Decimal("0.0000"),
                explanation=(
                    f"Only {len(expenses)} eligible expense transaction(s) spanning {coverage_days} day(s). "
                    "At least 3 expenses across 14+ days are required."
                ),
            ),
            Decimal("0.00"),
            {i: Decimal("1.00") for i in range(7)},
        )

    # Identify sources/names already modeled explicitly via confirmed future commitments to prevent double-counting
    scheduled_sources = {"bill_payment", "subscription_payment", "loan_payment"}
    scheduled_names = {c.name.lower() for c in confirmed_commitments}

    monthly_all: dict[str, Decimal] = {}
    monthly_non_scheduled: dict[str, Decimal] = {}
    dow_totals: dict[int, Decimal] = {i: Decimal("0.00") for i in range(7)}
    dow_counts: dict[int, int] = {i: 0 for i in range(7)}

    for tx in expenses:
        mk = _month_key(tx.transaction_date)
        amt = Decimal(tx.amount)
        monthly_all[mk] = monthly_all.get(mk, Decimal("0.00")) + amt

        desc_lower = ((tx.description or "") + " " + (tx.merchant_payee or "")).lower()
        is_already_scheduled = (tx.source in scheduled_sources) or any(
            len(name) >= 4 and name in desc_lower for name in scheduled_names
        )
        if not is_already_scheduled:
            monthly_non_scheduled[mk] = monthly_non_scheduled.get(mk, Decimal("0.00")) + amt
            dow = tx.transaction_date.weekday()
            dow_totals[dow] += amt
            dow_counts[dow] += 1

    ordered_all = sorted(monthly_all.items())
    ordered_disc = sorted(monthly_non_scheduled.items()) if monthly_non_scheduled else []

    all_weighted, hist_monthly_avg, trend_pct = _weighted_monthly_rate(ordered_all)
    disc_monthly, _, _ = _weighted_monthly_rate(ordered_disc)

    # Compute day-of-week index where sufficient observations exist
    avg_daily_total = sum(dow_totals.values(), Decimal("0.00"))
    dow_multipliers: dict[int, Decimal] = {i: Decimal("1.00") for i in range(7)}
    if len(expenses) >= 14 and avg_daily_total > Decimal("0.00"):
        mean_dow = avg_daily_total / Decimal("7")
        for i in range(7):
            if mean_dow > Decimal("0.00"):
                ratio = dow_totals[i] / mean_dow
                # Dampen multiplier to [0.5, 1.8]
                clamped = max(Decimal("0.50"), min(Decimal("1.80"), ratio))
                dow_multipliers[i] = _q2(clamped)

    # Use effective span across active days so short histories scale cleanly
    span_days = Decimal(str(max(30, min(180, coverage_days))))
    disc_sum = sum((v for _, v in ordered_disc), Decimal("0.00"))
    daily_from_span = _q2(disc_sum / span_days) if disc_sum > Decimal("0.00") else Decimal("0.00")
    daily_from_weighted = _q2(disc_monthly / Decimal("30"))
    daily_disc_rate = (
        daily_from_weighted
        if len(ordered_all) >= 2
        else (daily_from_span if coverage_days >= 20 else _q2(disc_sum / Decimal(str(max(14, coverage_days)))))
    )

    method = (
        "weighted_trend_seasonal_plus_commitments"
        if len(ordered_all) >= 3
        else ("weighted_moving_average_plus_commitments" if len(ordered_all) >= 2 else "rolling_daily_average")
    )

    predicted_disc = _q2(daily_disc_rate * Decimal(str(horizon_days)))
    predicted_total = _q2(predicted_disc + confirmed_total)

    conf = assess_forecast_confidence(
        observation_count=len(expenses),
        coverage_days=coverage_days,
        monthly_totals=[v for _, v in ordered_all],
        horizon_days=horizon_days,
        has_confirmed_schedules=bool(confirmed_commitments),
    )
    low, high = apply_confidence_bounds(predicted_total, conf.uncertainty_band_pct)

    monthly_disc_est = _q2(daily_disc_rate * Decimal("30"))
    # Extrapolated monthly commitment baseline if commitments exist in horizon
    monthly_comm_est = (
        _q2((confirmed_total / Decimal(str(horizon_days))) * Decimal("30"))
        if horizon_days > 0
        else Decimal("0.00")
    )
    next_month_est = _q2(monthly_disc_est + monthly_comm_est)
    next_week_est = _q2(daily_disc_rate * Decimal("7")) + sum(
        (
            c.expected_amount
            for c in confirmed_commitments
            if c.due_date <= as_of_date + dt.timedelta(days=7) and c.expected_amount is not None
        ),
        Decimal("0.00"),
    )
    quarterly_est = _q2(next_month_est * Decimal("3"))
    yearly_est = (
        _q2(next_month_est * Decimal("12"))
        if (coverage_days >= 60 or bool(confirmed_commitments))
        else None
    )

    recent_monthly = ordered_all[-1][1] if ordered_all else Decimal("0.00")
    explanation = (
        f"Based on {len(expenses)} non-transfer expenses over {coverage_days} days "
        f"(historical average INR {hist_monthly_avg:,.2f}/mo, trend {trend_pct:+}%) plus "
        f"INR {confirmed_total:,.2f} in confirmed upcoming obligations (with scheduled bill/subscription/EMI "
        "charges excluded from the discretionary base to avoid double-counting)."
    )

    return (
        ExpenseForecastResponse(
            horizon_days=horizon_days,
            method=method,
            confidence_label=conf.label,
            confidence_score=conf.score,
            predicted_total=predicted_total,
            lower_bound=low,
            upper_bound=high,
            historical_monthly_avg=hist_monthly_avg,
            recent_monthly_avg=_q2(recent_monthly),
            trend_pct=trend_pct,
            next_week_estimate=_q2(next_week_est),
            current_month_expected=next_month_est,
            next_month_estimate=next_month_est,
            quarterly_estimate=quarterly_est,
            yearly_estimate=yearly_est,
            explanation=explanation,
        ),
        daily_disc_rate,
        dow_multipliers,
    )


def forecast_income(
    *,
    incomes: list[FinancialTransaction],
    horizon_days: int,
) -> tuple[IncomeForecastResponse, Decimal]:
    """
    Forecast future income from verified non-transfer income history.
    Excludes loan disbursements/borrowed proceeds and handles irregular/missing income honestly.
    Returns (response, daily_income_rate).
    """
    eligible = [
        tx
        for tx in incomes
        if "loan disbursement" not in ((tx.description or "").lower())
        and "borrowed" not in ((tx.notes or "").lower())
    ]

    if not eligible:
        return (
            IncomeForecastResponse(
                horizon_days=horizon_days,
                method="insufficient_data",
                income_pattern="insufficient_data",
                confidence_label="insufficient_data",
                confidence_score=Decimal("0.0000"),
                observation_count=0,
                explanation="No eligible income transactions found; income cannot be projected reliably.",
            ),
            Decimal("0.00"),
        )

    dates = [tx.transaction_date for tx in eligible]
    coverage_days = ((max(dates) - min(dates)).days + 1) if len(dates) >= 2 else 1

    monthly_totals: dict[str, Decimal] = {}
    for tx in eligible:
        mk = _month_key(tx.transaction_date)
        monthly_totals[mk] = monthly_totals.get(mk, Decimal("0.00")) + Decimal(tx.amount)

    ordered = sorted(monthly_totals.items())
    vals = [float(v) for _, v in ordered]
    cv = (stdev(vals) / mean(vals)) if len(vals) >= 2 and mean(vals) > 0 else 1.0

    salary_hits = sum(
        1
        for tx in eligible
        if (tx.category and tx.category.name.lower() == "salary")
        or "salary" in ((tx.description or "").lower())
    )

    if len(ordered) >= 2 and cv <= 0.25:
        pattern = "regular_monthly" if salary_hits >= 2 else "multi_source_regular"
        method = "weighted_monthly_income"
    elif len(ordered) >= 2 or len(eligible) >= 2:
        pattern = "irregular"
        method = "historical_income_average"
    else:
        return (
            IncomeForecastResponse(
                horizon_days=horizon_days,
                method="insufficient_data",
                income_pattern="insufficient_data",
                confidence_label="insufficient_data",
                confidence_score=Decimal("0.0000"),
                historical_monthly_avg=_q2(Decimal(str(sum(vals)))),
                observation_count=len(eligible),
                explanation=(
                    f"Only {len(eligible)} income event over {coverage_days} day(s); at least 2 income cycles "
                    "are needed to distinguish regular salary from one-off receipts."
                ),
            ),
            Decimal("0.00"),
        )

    weighted_mo, hist_avg, _ = _weighted_monthly_rate(ordered)
    daily_rate = _q2(weighted_mo / Decimal("30"))
    predicted_total = _q2(daily_rate * Decimal(str(horizon_days)))

    conf = assess_forecast_confidence(
        observation_count=len(eligible),
        coverage_days=max(coverage_days, len(ordered) * 28),
        monthly_totals=[v for _, v in ordered],
        horizon_days=horizon_days,
        has_confirmed_schedules=(pattern in ("regular_monthly", "multi_source_regular")),
    )
    if pattern == "irregular" and conf.label == "high":
        from app.services.forecasting.forecast_confidence import ConfidenceAssessment

        conf = ConfidenceAssessment(
            label="low",
            score=Decimal("0.3800"),
            uncertainty_band_pct=Decimal("35.00"),
        )
    low, high = apply_confidence_bounds(predicted_total, conf.uncertainty_band_pct)

    explanation = (
        f"Classified income as '{pattern.replace('_', ' ')}' across {len(ordered)} month(s) and "
        f"{len(eligible)} verified non-transfer inflows (weighted rate INR {weighted_mo:,.2f}/mo)."
    )

    return (
        IncomeForecastResponse(
            horizon_days=horizon_days,
            method=method,
            income_pattern=pattern,
            confidence_label=conf.label,
            confidence_score=conf.score,
            predicted_total=predicted_total,
            lower_bound=low,
            upper_bound=high,
            monthly_estimate=weighted_mo,
            historical_monthly_avg=hist_avg,
            observation_count=len(eligible),
            explanation=explanation,
        ),
        daily_rate,
    )


def forecast_categories(
    *,
    expenses: list[FinancialTransaction],
    cat_map: dict,
    horizon_days: int,
) -> list[CategoryForecastItem]:
    """Forecast category-level spending strictly using actual Phase 8 / Finance category labels."""
    if not expenses:
        return []

    by_cat: dict[str, dict] = {}
    all_months: set[str] = set()
    for tx in expenses:
        mk = _month_key(tx.transaction_date)
        all_months.add(mk)
        cat_rec: TransactionCategorization | None = cat_map.get(tx.id)
        if tx.category is not None:
            cat_name = tx.category.name
            cat_id = str(tx.category.id)
        elif cat_rec and cat_rec.suggested_category_name:
            cat_name = cat_rec.suggested_category_name
            cat_id = str(cat_rec.suggested_category_id) if cat_rec.suggested_category_id else None
        else:
            cat_name = "Uncategorized"
            cat_id = None

        entry = by_cat.setdefault(
            cat_name,
            {"cat_id": cat_id, "monthly": {}, "count": 0, "dates": []},
        )
        entry["count"] += 1
        entry["dates"].append(tx.transaction_date)
        entry["monthly"][mk] = entry["monthly"].get(mk, Decimal("0.00")) + Decimal(tx.amount)

    num_months = max(1, len(all_months))
    horizon_factor = Decimal(str(horizon_days)) / Decimal("30")
    results: list[CategoryForecastItem] = []

    for cat_name, entry in by_cat.items():
        ordered = sorted(entry["monthly"].items())
        total_cat = sum((v for _, v in ordered), Decimal("0.00"))
        hist_avg = _q2(total_cat / Decimal(str(num_months)))
        recent_spend = ordered[-1][1]
        weighted_mo, _, _ = _weighted_monthly_rate(ordered)

        dates = entry["dates"]
        cov_days = ((max(dates) - min(dates)).days + 1) if len(dates) >= 2 else 1
        data_ok = entry["count"] >= 2 or cov_days >= 14

        if not data_ok:
            results.append(
                CategoryForecastItem(
                    category_id=entry["cat_id"],
                    category_name=cat_name,
                    historical_monthly_avg=hist_avg,
                    recent_monthly_spend=_q2(recent_spend),
                    predicted_amount=None,
                    expected_change_pct=None,
                    confidence_label="insufficient_data",
                    data_sufficient=False,
                    observation_count=entry["count"],
                    explanation=(
                        f"Only {entry['count']} transaction recorded in '{cat_name}'; more observations needed to predict."
                    ),
                )
            )
            continue

        # Smooth prediction between all-month average and active-month weighted rate
        blended_mo = _q2((hist_avg + weighted_mo) / Decimal("2"))
        predicted = _q2(blended_mo * horizon_factor)
        change_pct = Decimal("0.00")
        if hist_avg > Decimal("0.00"):
            change_pct = _q2(((blended_mo - hist_avg) / hist_avg) * Decimal("100"))

        conf = assess_forecast_confidence(
            observation_count=entry["count"],
            coverage_days=max(cov_days, len(ordered) * 28),
            monthly_totals=[v for _, v in ordered],
            horizon_days=horizon_days,
        )
        low, high = apply_confidence_bounds(predicted, conf.uncertainty_band_pct)
        direction = "higher" if change_pct > Decimal("5.00") else ("lower" if change_pct < Decimal("-5.00") else "in line with")
        explanation = (
            f"Predicted '{cat_name}' spend is {direction} historical monthly average "
            f"(INR {hist_avg:,.2f}/mo) across {entry['count']} observations."
        )
        results.append(
            CategoryForecastItem(
                category_id=entry["cat_id"],
                category_name=cat_name,
                historical_monthly_avg=hist_avg,
                recent_monthly_spend=_q2(recent_spend),
                predicted_amount=predicted,
                lower_bound=low,
                upper_bound=high,
                expected_change_pct=change_pct,
                confidence_label=conf.label,
                data_sufficient=True,
                observation_count=entry["count"],
                explanation=explanation,
            )
        )

    results.sort(
        key=lambda x: (x.predicted_amount if x.predicted_amount is not None else Decimal("-1"), x.historical_monthly_avg),
        reverse=True,
    )
    return results
