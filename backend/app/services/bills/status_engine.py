import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.bills import Bill

DEFAULT_TZ = "Asia/Kolkata"


def resolve_user_today(user_timezone: str | None = None) -> dt.date:
    """Returns today's calendar date in the user's configured timezone (defaults to Asia/Kolkata)."""
    tz_name = user_timezone or DEFAULT_TZ
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo(DEFAULT_TZ)
    return dt.datetime.now(tz).date()


def resolve_user_zone(user_timezone: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(user_timezone or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def get_effective_target_amount(bill: Bill) -> Decimal | None:
    """
    Returns known target amount for a bill:
    - If current_amount is set -> returns current_amount.
    - Else if not is_variable_amount and expected_amount is set -> returns expected_amount.
    - Else -> returns None (variable bill without confirmed bill amount yet).
    """
    if bill.current_amount is not None:
        return Decimal(bill.current_amount)
    if not bill.is_variable_amount and bill.expected_amount is not None:
        return Decimal(bill.expected_amount)
    return None


def compute_remaining_due(bill: Bill) -> Decimal | None:
    """
    Calculates remaining amount due without ever silently coercing unknown variable amounts to 0.
    Returns Decimal('0.00') when settled/paid, or None if variable amount is unknown and unpaid.
    """
    if bill.stored_status == "paid":
        return Decimal("0.00")
    target = get_effective_target_amount(bill)
    if target is None:
        return None
    paid = Decimal(bill.amount_paid_total or Decimal("0.00"))
    remaining = target - paid
    return remaining if remaining > Decimal("0.00") else Decimal("0.00")


def compute_bill_derived_status(
    bill: Bill,
    today: dt.date | None = None,
    due_soon_days: int | None = None,
    user_timezone: str | None = None,
) -> str:
    """
    Deterministic bill status engine:
      - archived: inactive or archived
      - paid: stored_status == 'paid' OR (known positive target AND amount_paid_total >= target)
        -> Never flips back to overdue even after due_date passes.
      - overdue: unpaid/partially_paid and due_date < today
      - due_soon: unpaid/partially_paid and 0 <= (due_date - today).days <= threshold
      - upcoming: unpaid/partially_paid and due_date > today + threshold
    """
    if not bill.is_active or bill.stored_status == "archived":
        return "archived"

    target = get_effective_target_amount(bill)
    paid = Decimal(bill.amount_paid_total or Decimal("0.00"))
    if bill.stored_status == "paid" or (
        target is not None and target > Decimal("0.00") and paid >= target
    ):
        return "paid"

    ref_today = today or resolve_user_today(user_timezone)
    threshold = (
        due_soon_days if due_soon_days is not None else settings.BILL_DUE_SOON_DAYS
    )
    delta_days = (bill.due_date - ref_today).days

    if delta_days < 0:
        return "overdue"
    if delta_days <= threshold:
        return "due_soon"
    return "upcoming"
