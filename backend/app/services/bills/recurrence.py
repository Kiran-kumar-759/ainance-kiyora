import calendar
import datetime as dt


def _add_months_with_anchor(base_date: dt.date, months: int, anchor_day: int) -> dt.date:
    """
    Advances base_date by `months` while preserving `anchor_day` where valid
    (e.g., anchor_day=31: Jan 31 -> Feb 28/29 -> Mar 31, never drifting permanently to 28th).
    """
    total_months = (base_date.year * 12 + (base_date.month - 1)) + months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1
    _, max_day = calendar.monthrange(new_year, new_month)
    clamped_day = min(max(1, anchor_day), max_day)
    return dt.date(new_year, new_month, clamped_day)


def advance_due_date(
    current_due: dt.date,
    frequency: str,
    anchor_day: int | None = None,
    custom_interval_days: int | None = None,
) -> dt.date:
    """Computes the next deterministic due date for recurring schedules."""
    anchor = anchor_day or current_due.day
    if frequency == "weekly":
        return current_due + dt.timedelta(days=7)
    if frequency == "monthly":
        return _add_months_with_anchor(current_due, 1, anchor)
    if frequency == "quarterly":
        return _add_months_with_anchor(current_due, 3, anchor)
    if frequency == "half_yearly":
        return _add_months_with_anchor(current_due, 6, anchor)
    if frequency == "yearly":
        return _add_months_with_anchor(current_due, 12, anchor)
    if frequency == "custom":
        days = max(1, custom_interval_days or 30)
        return current_due + dt.timedelta(days=days)
    raise ValueError(f"Unsupported recurrence frequency: {frequency}")


def compute_billing_period_for_due(
    due_date: dt.date,
    frequency: str | None,
) -> tuple[dt.date | None, dt.date | None]:
    """Derives sensible billing period start/end around a due date for recurring occurrences."""
    if not frequency:
        return None, None
    if frequency == "weekly":
        return due_date - dt.timedelta(days=6), due_date
    if frequency == "monthly":
        prev = _add_months_with_anchor(due_date, -1, due_date.day)
        return prev + dt.timedelta(days=1), due_date
    if frequency == "quarterly":
        prev = _add_months_with_anchor(due_date, -3, due_date.day)
        return prev + dt.timedelta(days=1), due_date
    if frequency == "half_yearly":
        prev = _add_months_with_anchor(due_date, -6, due_date.day)
        return prev + dt.timedelta(days=1), due_date
    if frequency == "yearly":
        prev = _add_months_with_anchor(due_date, -12, due_date.day)
        return prev + dt.timedelta(days=1), due_date
    return None, None
