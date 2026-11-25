import calendar
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.schemas.analytics.common import ComparisonMetric, PeriodBounds

IST_TZ = ZoneInfo("Asia/Kolkata")
TWO_PLACES = Decimal("0.01")

SUPPORTED_PERIODS = {
    "this_week",
    "this_month",
    "last_month",
    "last_3_months",
    "last_6_months",
    "this_quarter",
    "last_quarter",
    "this_year",
    "last_year",
    "all_time",
    "custom",
}


def ist_now() -> dt.datetime:
    """Returns current timestamp in Asia/Kolkata timezone."""
    return dt.datetime.now(IST_TZ)


def ist_today() -> dt.date:
    """Returns today's calendar date in Asia/Kolkata timezone."""
    return ist_now().date()


def quantize_money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_savings_rate(income: Decimal, expenses: Decimal) -> tuple[Decimal, Decimal | None]:
    """
    Returns (net_savings, savings_rate_pct).
    Safely returns None for savings_rate_pct when income <= 0 to prevent division by zero.
    """
    net_savings = quantize_money(income - expenses)
    if income <= Decimal("0.00"):
        return net_savings, None
    rate = ((net_savings / income) * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return net_savings, rate


def compute_comparison_metric(current: Decimal, previous: Decimal) -> ComparisonMetric:
    """Deterministic period-over-period comparison with safe zero-baseline handling."""
    cur = quantize_money(current)
    prev = quantize_money(previous)
    diff = quantize_money(cur - prev)

    if diff > Decimal("0.00"):
        direction = "up"
    elif diff < Decimal("0.00"):
        direction = "down"
    else:
        direction = "flat"

    if prev == Decimal("0.00"):
        return ComparisonMetric(
            current_value=cur,
            previous_value=prev,
            absolute_difference=diff,
            percentage_change=None,
            trend_direction=direction,
            is_zero_baseline=True,
            comparison_note="Percentage change unavailable because the previous period total is ₹0.00.",
        )

    pct = ((diff / abs(prev)) * Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    return ComparisonMetric(
        current_value=cur,
        previous_value=prev,
        absolute_difference=diff,
        percentage_change=pct,
        trend_direction=direction,
        is_zero_baseline=False,
        comparison_note=None,
    )


def _subtract_months(year: int, month: int, delta_months: int) -> tuple[int, int]:
    total_months = (year * 12 + (month - 1)) - delta_months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    return new_year, new_month


def _month_end(year: int, month: int) -> dt.date:
    _, last_day = calendar.monthrange(year, month)
    return dt.date(year, month, last_day)


def resolve_period_bounds(
    period: str = "this_month",
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    earliest_date: dt.date | None = None,
    reference_today: dt.date | None = None,
) -> PeriodBounds:
    """
    Resolves deterministic inclusive date bounds in Asia/Kolkata for supported period presets
    or validated custom start/end dates.
    """
    if period not in SUPPORTED_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported period '{period}'. Supported values: {', '.join(sorted(SUPPORTED_PERIODS))}.",
        )

    today = reference_today or ist_today()

    if period == "custom":
        if start_date is None or end_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date are required when period='custom'.",
            )
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date cannot be after end_date.",
            )
        s_date, e_date = start_date, end_date
        label = f"Custom ({s_date.strftime('%d/%m/%Y')} - {e_date.strftime('%d/%m/%Y')})"
        is_partial = s_date <= today < e_date
    elif period == "this_week":
        s_date = today - dt.timedelta(days=today.weekday())  # Monday
        e_date = s_date + dt.timedelta(days=6)  # Sunday
        label = "This Week"
        is_partial = today < e_date
    elif period == "this_month":
        s_date = today.replace(day=1)
        e_date = _month_end(today.year, today.month)
        label = f"This Month ({today.strftime('%b %Y')})"
        is_partial = today < e_date
    elif period == "last_month":
        y, m = _subtract_months(today.year, today.month, 1)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(y, m)
        label = f"Last Month ({s_date.strftime('%b %Y')})"
        is_partial = False
    elif period == "last_3_months":
        y, m = _subtract_months(today.year, today.month, 2)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(today.year, today.month)
        label = "Last 3 Months"
        is_partial = today < e_date
    elif period == "last_6_months":
        y, m = _subtract_months(today.year, today.month, 5)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(today.year, today.month)
        label = "Last 6 Months"
        is_partial = today < e_date
    elif period == "this_quarter":
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        s_date = dt.date(today.year, q_start_month, 1)
        e_date = _month_end(today.year, q_start_month + 2)
        q_num = ((today.month - 1) // 3) + 1
        label = f"Q{q_num} {today.year}"
        is_partial = today < e_date
    elif period == "last_quarter":
        cur_q_start = ((today.month - 1) // 3) * 3 + 1
        y, m = _subtract_months(today.year, cur_q_start, 3)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(y, m + 2)
        q_num = ((m - 1) // 3) + 1
        label = f"Q{q_num} {y}"
        is_partial = False
    elif period == "this_year":
        s_date = dt.date(today.year, 1, 1)
        e_date = dt.date(today.year, 12, 31)
        label = f"This Year ({today.year})"
        is_partial = today < e_date
    elif period == "last_year":
        s_date = dt.date(today.year - 1, 1, 1)
        e_date = dt.date(today.year - 1, 12, 31)
        label = f"Last Year ({today.year - 1})"
        is_partial = False
    else:  # all_time
        s_date = min(earliest_date, today) if earliest_date else dt.date(today.year, 1, 1)
        e_date = today
        label = "All Time"
        is_partial = False

    days_in_period = (e_date - s_date).days + 1
    if today < s_date:
        elapsed_days = 0
    elif today >= e_date:
        elapsed_days = days_in_period
    else:
        elapsed_days = (today - s_date).days + 1

    return PeriodBounds(
        period=period,
        label=label,
        start_date=s_date,
        end_date=e_date,
        timezone="Asia/Kolkata",
        is_partial_period=is_partial,
        days_in_period=days_in_period,
        elapsed_days=elapsed_days,
    )


def resolve_previous_period_bounds(
    current: PeriodBounds, reference_today: dt.date | None = None
) -> PeriodBounds:
    """Resolves the matching preceding comparison period cleanly."""
    today = reference_today or ist_today()
    p = current.period

    if p == "this_month":
        return resolve_period_bounds("last_month", reference_today=today)
    if p == "last_month":
        y, m = _subtract_months(current.start_date.year, current.start_date.month, 1)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(y, m)
        return PeriodBounds(
            period="previous_month",
            label=s_date.strftime("%b %Y"),
            start_date=s_date,
            end_date=e_date,
            timezone="Asia/Kolkata",
            is_partial_period=False,
            days_in_period=(e_date - s_date).days + 1,
            elapsed_days=(e_date - s_date).days + 1,
        )
    if p == "this_quarter":
        return resolve_period_bounds("last_quarter", reference_today=today)
    if p == "last_quarter":
        y, m = _subtract_months(current.start_date.year, current.start_date.month, 3)
        s_date = dt.date(y, m, 1)
        e_date = _month_end(y, m + 2)
        q_num = ((m - 1) // 3) + 1
        return PeriodBounds(
            period="previous_quarter",
            label=f"Q{q_num} {y}",
            start_date=s_date,
            end_date=e_date,
            timezone="Asia/Kolkata",
            is_partial_period=False,
            days_in_period=(e_date - s_date).days + 1,
            elapsed_days=(e_date - s_date).days + 1,
        )
    if p == "this_year":
        return resolve_period_bounds("last_year", reference_today=today)
    if p in {"last_3_months", "last_6_months"}:
        span_months = 3 if p == "last_3_months" else 6
        prev_end = current.start_date - dt.timedelta(days=1)
        sy, sm = _subtract_months(current.start_date.year, current.start_date.month, span_months)
        s_date = dt.date(sy, sm, 1)
        days = (prev_end - s_date).days + 1
        return PeriodBounds(
            period=f"previous_{span_months}_months",
            label=f"Preceding {span_months} Months",
            start_date=s_date,
            end_date=prev_end,
            timezone="Asia/Kolkata",
            is_partial_period=False,
            days_in_period=days,
            elapsed_days=days,
        )

    # Equal-length preceding period for custom, this_week, last_year, all_time
    span_days = current.days_in_period
    prev_end = current.start_date - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=span_days - 1)
    return PeriodBounds(
        period="previous_custom",
        label=f"Preceding ({prev_start.strftime('%d/%m/%Y')} - {prev_end.strftime('%d/%m/%Y')})",
        start_date=prev_start,
        end_date=prev_end,
        timezone="Asia/Kolkata",
        is_partial_period=False,
        days_in_period=span_days,
        elapsed_days=span_days,
    )


def choose_granularity(
    start_date: dt.date, end_date: dt.date, requested: str | None = None
) -> str:
    """Picks daily, weekly, monthly, or quarterly aggregation based on date range."""
    valid = {"day", "week", "month", "quarter"}
    if requested:
        norm = {
            "daily": "day",
            "day": "day",
            "weekly": "week",
            "week": "week",
            "monthly": "month",
            "month": "month",
            "quarterly": "quarter",
            "quarter": "quarter",
        }.get(requested.lower(), requested.lower())
        if norm not in valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid granularity. Use daily, weekly, monthly, or quarterly.",
            )
        return norm

    span = (end_date - start_date).days + 1
    if span <= 35:
        return "day"
    if span <= 120:
        return "week"
    if span <= 730:
        return "month"
    return "quarter"
