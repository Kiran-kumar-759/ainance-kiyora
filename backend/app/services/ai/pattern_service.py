import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intelligence import (
    MerchantIdentity,
    RecurringPaymentCandidate,
    TransactionCategorization,
)
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.intelligence import (
    DayOfWeekSpendingPoint,
    MonthlySpendingPoint,
    SpendingPatternGroupItem,
    SpendingPatternsResponse,
    WeeklySpendingPoint,
)
from app.services.ai.merchant_intelligence import normalize_merchant_text

ESSENTIAL_CATEGORIES = {
    "groceries",
    "housing & rent",
    "utilities & bills",
    "healthcare",
    "education",
    "insurance",
    "transportation",
    "loan interest",
}

FIXED_CATEGORIES = {
    "housing & rent",
    "subscriptions",
    "insurance",
    "loan interest",
}

DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole <= Decimal("0.00"):
        return Decimal("0.00")
    return ((part / whole) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_spending_patterns(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> SpendingPatternsResponse:
    """
    Compute deterministic, ledger-accurate spending patterns using Decimal arithmetic
    and Phase 4 active-journal/non-transfer transaction semantics.
    """
    today = dt.date.today()
    end_date = date_to or today
    start_date = date_from or (end_date - dt.timedelta(days=180))

    txs = repo.list_eligible_transactions(
        db,
        user_id,
        date_from=start_date,
        date_to=end_date,
        include_transfers=False,
    )

    cat_map = {
        c.transaction_id: c
        for c in db.execute(
            select(TransactionCategorization).where(TransactionCategorization.user_id == user_id)
        )
        .scalars()
        .all()
    }
    merchant_map = {
        m.id: m
        for m in db.execute(
            select(MerchantIdentity).where(MerchantIdentity.user_id == user_id)
        )
        .scalars()
        .all()
    }
    recurring_keys = {
        r.merchant_key
        for r in db.execute(
            select(RecurringPaymentCandidate).where(
                RecurringPaymentCandidate.user_id == user_id,
                RecurringPaymentCandidate.review_status != "rejected",
            )
        )
        .scalars()
        .all()
    }

    total_expense = Decimal("0.00")
    total_income = Decimal("0.00")
    recurring_total = Decimal("0.00")
    non_recurring_total = Decimal("0.00")
    fixed_total = Decimal("0.00")
    variable_total = Decimal("0.00")
    essential_total = Decimal("0.00")
    discretionary_total = Decimal("0.00")
    weekend_expense = Decimal("0.00")
    weekday_expense = Decimal("0.00")

    by_category: dict[str, list] = {}
    by_merchant: dict[str, list] = {}
    monthly_buckets: dict[str, dict] = {}
    weekly_buckets: dict[dt.date, dict] = {}
    dow_buckets: dict[int, dict] = {
        i: {"amount": Decimal("0.00"), "count": 0} for i in range(7)
    }

    for tx in txs:
        amt = Decimal(tx.amount or Decimal("0.00"))
        month_key = tx.transaction_date.strftime("%Y-%m")
        m_bucket = monthly_buckets.setdefault(
            month_key,
            {
                "expense": Decimal("0.00"),
                "income": Decimal("0.00"),
                "recurring": Decimal("0.00"),
                "non_recurring": Decimal("0.00"),
                "count": 0,
            },
        )

        if tx.transaction_type == "income":
            total_income += amt
            m_bucket["income"] += amt
            continue

        total_expense += amt
        m_bucket["expense"] += amt
        m_bucket["count"] += 1

        cat_rec = cat_map.get(tx.id)
        cat_name = (
            (tx.category.name if tx.category else None)
            or (cat_rec.suggested_category_name if cat_rec else None)
            or "Uncategorized"
        )
        merchant_obj = merchant_map.get(cat_rec.merchant_id) if (cat_rec and cat_rec.merchant_id) else None
        if merchant_obj is not None:
            m_key = merchant_obj.canonical_key
            m_name = merchant_obj.normalized_name
        else:
            parsed = normalize_merchant_text(tx.description, tx.merchant_payee)
            m_key = parsed.canonical_key
            m_name = parsed.normalized_name

        # Category & merchant sums
        c_entry = by_category.setdefault(cat_name, [Decimal("0.00"), 0])
        c_entry[0] += amt
        c_entry[1] += 1

        m_entry = by_merchant.setdefault(m_name, [Decimal("0.00"), 0])
        m_entry[0] += amt
        m_entry[1] += 1

        # Recurring vs non-recurring
        is_recurring = m_key in recurring_keys or cat_name.lower() in {"subscriptions", "loan interest"}
        if is_recurring:
            recurring_total += amt
            m_bucket["recurring"] += amt
        else:
            non_recurring_total += amt
            m_bucket["non_recurring"] += amt

        # Fixed vs variable
        if cat_name.lower() in FIXED_CATEGORIES or is_recurring:
            fixed_total += amt
        else:
            variable_total += amt

        # Essential vs discretionary
        if cat_name.lower() in ESSENTIAL_CATEGORIES:
            essential_total += amt
        else:
            discretionary_total += amt

        # Weekend vs weekday
        dow = tx.transaction_date.weekday()
        if dow >= 5:
            weekend_expense += amt
        else:
            weekday_expense += amt
        dow_buckets[dow]["amount"] += amt
        dow_buckets[dow]["count"] += 1

        # Weekly bucket (Monday start)
        week_start = tx.transaction_date - dt.timedelta(days=dow)
        w_bucket = weekly_buckets.setdefault(
            week_start, {"amount": Decimal("0.00"), "count": 0}
        )
        w_bucket["amount"] += amt
        w_bucket["count"] += 1

    cat_items = sorted(
        [
            SpendingPatternGroupItem(
                label=k,
                amount=v[0].quantize(Decimal("0.01")),
                transaction_count=v[1],
                share_pct=_pct(v[0], total_expense),
            )
            for k, v in by_category.items()
        ],
        key=lambda x: x.amount,
        reverse=True,
    )

    merch_items = sorted(
        [
            SpendingPatternGroupItem(
                label=k,
                amount=v[0].quantize(Decimal("0.01")),
                transaction_count=v[1],
                share_pct=_pct(v[0], total_expense),
            )
            for k, v in by_merchant.items()
        ],
        key=lambda x: x.amount,
        reverse=True,
    )

    top_1 = merch_items[0].amount if merch_items else Decimal("0.00")
    top_3 = sum((m.amount for m in merch_items[:3]), Decimal("0.00"))

    monthly_trend = [
        MonthlySpendingPoint(
            month=m,
            total_expense=b["expense"].quantize(Decimal("0.01")),
            total_income=b["income"].quantize(Decimal("0.01")),
            recurring_expense=b["recurring"].quantize(Decimal("0.01")),
            non_recurring_expense=b["non_recurring"].quantize(Decimal("0.01")),
            transaction_count=b["count"],
        )
        for m, b in sorted(monthly_buckets.items())
    ]

    weekly_trend = [
        WeeklySpendingPoint(
            week_start=wk,
            total_expense=b["amount"].quantize(Decimal("0.01")),
            transaction_count=b["count"],
        )
        for wk, b in sorted(weekly_buckets.items())[-12:]
    ]

    dow_trend = [
        DayOfWeekSpendingPoint(
            day_name=DAY_NAMES[i],
            day_index=i,
            total_expense=dow_buckets[i]["amount"].quantize(Decimal("0.01")),
            transaction_count=dow_buckets[i]["count"],
        )
        for i in range(7)
    ]

    return SpendingPatternsResponse(
        period_start=start_date,
        period_end=end_date,
        total_expense=total_expense.quantize(Decimal("0.01")),
        total_income=total_income.quantize(Decimal("0.01")),
        recurring_total=recurring_total.quantize(Decimal("0.01")),
        non_recurring_total=non_recurring_total.quantize(Decimal("0.01")),
        fixed_total=fixed_total.quantize(Decimal("0.01")),
        variable_total=variable_total.quantize(Decimal("0.01")),
        essential_total=essential_total.quantize(Decimal("0.01")),
        discretionary_total=discretionary_total.quantize(Decimal("0.01")),
        weekend_expense=weekend_expense.quantize(Decimal("0.01")),
        weekday_expense=weekday_expense.quantize(Decimal("0.01")),
        weekend_share_pct=_pct(weekend_expense, total_expense),
        top_merchant_concentration_pct=_pct(top_1, total_expense),
        top_3_merchant_concentration_pct=_pct(top_3, total_expense),
        by_category=cat_items[:15],
        by_merchant=merch_items[:15],
        monthly_trend=monthly_trend,
        weekly_trend=weekly_trend,
        day_of_week_trend=dow_trend,
    )
