import calendar
import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.bills import Bill, BillRecurrenceSchedule
from app.repositories.forecasting.forecast_repository import ForecastRepository
from app.schemas.forecasting import CommitmentForecastItem


def _advance_date(base: dt.date, anchor_day: int, freq: str, custom_days: int | None = None) -> dt.date:
    if freq == "weekly":
        return base + dt.timedelta(days=7)
    if freq == "custom":
        return base + dt.timedelta(days=max(1, custom_days or 30))
    months = {"monthly": 1, "quarterly": 3, "half_yearly": 6, "yearly": 12}.get(freq, 1)
    y = base.year + (base.month - 1 + months) // 12
    m = (base.month - 1 + months) % 12 + 1
    max_day = calendar.monthrange(y, m)[1]
    return dt.date(y, m, min(max(1, anchor_day), max_day))


def collect_upcoming_commitments(
    db: Session,
    repo: ForecastRepository,
    user_id: uuid.UUID,
    *,
    as_of_date: dt.date,
    horizon_days: int,
    cancelled_subscription_ids: set[str] | None = None,
) -> tuple[list[CommitmentForecastItem], Decimal, int]:
    """
    Gather future bills, recurrence schedules, active subscriptions, loan EMIs,
    and unconfirmed Phase 8 recurring candidates up to as_of_date + horizon_days.

    Unknown variable bills remain explicit None (amount_certainty='unknown_amount').
    Unconfirmed Phase 8 candidates are kept strictly separate and excluded from confirmed totals.
    Returns: (items, confirmed_total, unknown_variable_count)
    """
    end_date = as_of_date + dt.timedelta(days=horizon_days)
    cancelled_ids = cancelled_subscription_ids or set()
    items: list[CommitmentForecastItem] = []

    accounts = {str(a.id): a.name for a in repo.list_active_accounts(db, user_id)}
    seen_bill_schedule_dates: set[tuple[str, dt.date]] = set()

    # 1. Existing open Bills (Phase 5)
    bills: list[Bill] = repo.list_open_bills(db, user_id, cutoff_end=end_date)
    for b in bills:
        if b.due_date < as_of_date - dt.timedelta(days=30):
            continue
        due = max(b.due_date, as_of_date)
        raw_amt = b.current_amount if b.current_amount is not None else b.expected_amount
        remaining: Decimal | None = None
        certainty = "confirmed_fixed"
        if raw_amt is not None:
            remaining = max(Decimal("0.00"), Decimal(raw_amt) - Decimal(b.amount_paid_total or Decimal("0.00")))
            if b.is_variable_amount and b.current_amount is None:
                certainty = "estimated_variable"
        else:
            certainty = "unknown_amount"

        if b.parent_schedule_id:
            seen_bill_schedule_dates.add((str(b.parent_schedule_id), b.due_date))

        items.append(
            CommitmentForecastItem(
                source_type="bill",
                source_id=str(b.id),
                name=b.bill_name,
                due_date=due,
                frequency=b.frequency or "one_time",
                expected_amount=remaining,
                amount_certainty=certainty,
                commitment_status="confirmed",
                category_name=b.financial_category.name if b.financial_category else "Utilities & Bills",
                account_id=str(b.linked_account_id) if b.linked_account_id else None,
                account_name=accounts.get(str(b.linked_account_id)) if b.linked_account_id else None,
            )
        )

    # 2. Future projected occurrences from BillRecurrenceSchedules (excluding dates already instantiated as Bills)
    schedules: list[BillRecurrenceSchedule] = repo.list_active_bill_schedules(db, user_id)
    for sched in schedules:
        cur = sched.next_due_date
        steps = 0
        while cur <= end_date and steps < 60:
            steps += 1
            if sched.end_date and cur > sched.end_date:
                break
            if cur >= as_of_date and (str(sched.id), cur) not in seen_bill_schedule_dates:
                amt = Decimal(sched.expected_amount) if sched.expected_amount is not None else None
                certainty = (
                    "unknown_amount"
                    if amt is None
                    else ("estimated_variable" if sched.is_variable_amount else "confirmed_fixed")
                )
                items.append(
                    CommitmentForecastItem(
                        source_type="bill_schedule",
                        source_id=str(sched.id),
                        name=sched.bill_name,
                        due_date=cur,
                        frequency=sched.frequency,
                        expected_amount=amt,
                        amount_certainty=certainty,
                        commitment_status="confirmed",
                        category_name="Utilities & Bills",
                        account_id=str(sched.linked_account_id) if sched.linked_account_id else None,
                        account_name=accounts.get(str(sched.linked_account_id))
                        if sched.linked_account_id
                        else None,
                    )
                )
            nxt = _advance_date(cur, sched.anchor_day, sched.frequency, sched.custom_interval_days)
            if nxt <= cur:
                break
            cur = nxt

    # 3. Active / Trial Subscriptions (Phase 6)
    subs = repo.list_active_subscriptions(db, user_id)
    for sub in subs:
        if str(sub.id) in cancelled_ids:
            continue
        cur = sub.next_renewal_date or sub.trial_end_date
        if cur is None:
            continue
        steps = 0
        while cur <= end_date and steps < 60:
            steps += 1
            if cur >= as_of_date:
                amt = Decimal(sub.amount) if sub.amount is not None else None
                items.append(
                    CommitmentForecastItem(
                        source_type="subscription",
                        source_id=str(sub.id),
                        name=sub.subscription_name,
                        due_date=cur,
                        frequency=sub.billing_frequency,
                        expected_amount=amt,
                        amount_certainty="confirmed_fixed" if amt is not None else "unknown_amount",
                        commitment_status="confirmed",
                        category_name="Subscriptions",
                        account_id=str(sub.linked_account_id) if sub.linked_account_id else None,
                        account_name=accounts.get(str(sub.linked_account_id))
                        if sub.linked_account_id
                        else None,
                    )
                )
            nxt = _advance_date(
                cur, sub.anchor_day, sub.billing_frequency, sub.custom_interval_days
            )
            if nxt <= cur:
                break
            cur = nxt

    # 4. Active Loan EMIs (Phase 6)
    loans_with_insts = repo.list_active_loans_with_installments(db, user_id, cutoff_end=end_date)
    for loan, insts in loans_with_insts:
        if insts:
            for inst in insts:
                if inst.due_date < as_of_date - dt.timedelta(days=30):
                    continue
                paid_so_far = Decimal(inst.principal_paid or Decimal("0.00")) + Decimal(
                    inst.interest_paid or Decimal("0.00")
                )
                rem = max(Decimal("0.00"), Decimal(inst.emi_amount) - paid_so_far)
                items.append(
                    CommitmentForecastItem(
                        source_type="loan_installment",
                        source_id=str(inst.id),
                        name=f"{loan.loan_name} EMI #{inst.installment_number}",
                        due_date=max(inst.due_date, as_of_date),
                        frequency=loan.emi_frequency,
                        expected_amount=rem,
                        amount_certainty="confirmed_fixed",
                        commitment_status="confirmed",
                        category_name="Loan Interest",
                        account_id=str(loan.linked_repayment_account_id)
                        if loan.linked_repayment_account_id
                        else None,
                        account_name=accounts.get(str(loan.linked_repayment_account_id))
                        if loan.linked_repayment_account_id
                        else None,
                    )
                )
        elif loan.next_emi_due_date and loan.next_emi_due_date <= end_date:
            cur = loan.next_emi_due_date
            steps = 0
            while cur <= end_date and steps < 24:
                steps += 1
                if cur >= as_of_date:
                    items.append(
                        CommitmentForecastItem(
                            source_type="loan_installment",
                            source_id=str(loan.id),
                            name=f"{loan.loan_name} EMI",
                            due_date=cur,
                            frequency=loan.emi_frequency,
                            expected_amount=Decimal(loan.emi_amount),
                            amount_certainty="confirmed_fixed",
                            commitment_status="confirmed",
                            category_name="Loan Interest",
                            account_id=str(loan.linked_repayment_account_id)
                            if loan.linked_repayment_account_id
                            else None,
                            account_name=accounts.get(str(loan.linked_repayment_account_id))
                            if loan.linked_repayment_account_id
                            else None,
                        )
                    )
                cur = _advance_date(cur, loan.anchor_day, loan.emi_frequency)

    # 5. Unconfirmed Phase 8 Recurring Candidates (surface transparently, never mix as confirmed)
    for cand in repo.list_pending_recurring_candidates(db, user_id):
        if cand.next_expected_date and as_of_date <= cand.next_expected_date <= end_date:
            items.append(
                CommitmentForecastItem(
                    source_type="recurring_candidate",
                    source_id=str(cand.id),
                    name=f"{cand.merchant_name} (Candidate)",
                    due_date=cand.next_expected_date,
                    frequency=cand.frequency,
                    expected_amount=Decimal(cand.estimated_amount),
                    amount_certainty="unconfirmed_candidate",
                    commitment_status="unconfirmed_candidate",
                    category_name=cand.suggested_category_name,
                )
            )

    items.sort(key=lambda c: (c.due_date, c.commitment_status != "confirmed"))
    confirmed_total = sum(
        (
            c.expected_amount
            for c in items
            if c.commitment_status == "confirmed" and c.expected_amount is not None
        ),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    unknown_count = sum(
        1
        for c in items
        if c.commitment_status == "confirmed" and c.expected_amount is None
    )
    return items, confirmed_total, unknown_count
