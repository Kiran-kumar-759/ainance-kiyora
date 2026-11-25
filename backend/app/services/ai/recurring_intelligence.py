import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intelligence import (
    MerchantIdentity,
    RecurringPaymentCandidate,
    TransactionCategorization,
)
from app.models.subscriptions import Subscription
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.services.ai.merchant_intelligence import normalize_merchant_text

_FREQUENCY_WINDOWS: tuple[tuple[str, int, int, int], ...] = (
    ("weekly", 5, 9, 7),
    ("monthly", 24, 37, 30),
    ("quarterly", 78, 105, 91),
    ("half_yearly", 165, 198, 182),
    ("yearly", 340, 390, 365),
)

_SUBSCRIPTION_CATS = {"subscriptions", "entertainment"}
_UTILITY_CATS = {"utilities & bills"}
_HOUSING_EMI_CATS = {"housing & rent", "loan interest", "insurance"}


def _classify_frequency(intervals: list[int]) -> tuple[str, int] | None:
    if not intervals:
        return None
    med_gap = median(intervals)
    for freq, low, high, step_days in _FREQUENCY_WINDOWS:
        if low <= med_gap <= high:
            return freq, step_days
    return None


def _commitment_type(cat_name: str | None, variability_pct: Decimal) -> str:
    lower = (cat_name or "").lower()
    if lower in _SUBSCRIPTION_CATS:
        return "subscription"
    if lower in _UTILITY_CATS:
        return "variable_utility" if variability_pct > Decimal("10.00") else "utility_bill"
    if lower in _HOUSING_EMI_CATS:
        return "fixed_commitment"
    return "variable_recurring" if variability_pct > Decimal("12.00") else "recurring_payment"


def _add_frequency(last_date: dt.date, frequency: str, step_days: int) -> dt.date:
    return last_date + dt.timedelta(days=step_days)


def detect_recurring_payments_for_user(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    *,
    lookback_days: int = 540,
) -> list[RecurringPaymentCandidate]:
    """
    Detect recurring fixed & variable expense patterns from active ledger transactions
    and reconcile against existing Phase 6 Subscriptions without creating fake subscriptions.
    """
    since_date = dt.date.today() - dt.timedelta(days=lookback_days)
    txs = repo.list_eligible_transactions(
        db, user_id, date_from=since_date, include_transfers=False
    )
    expenses = [tx for tx in txs if tx.transaction_type == "expense"]

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
    subs = list(
        db.execute(select(Subscription).where(Subscription.user_id == user_id))
        .scalars()
        .all()
    )
    existing_candidates = {
        (c.merchant_key, c.frequency): c
        for c in repo.list_recurring_candidates(db, user_id)
    }

    # Build normalized subscription lookup for cross-referencing Phase 6
    sub_by_key: dict[str, Subscription] = {}
    for sub in subs:
        k1 = normalize_merchant_text(sub.subscription_name, sub.provider_name).canonical_key
        sub_by_key[k1] = sub
        if sub.provider_name:
            k2 = normalize_merchant_text(sub.provider_name, sub.provider_name).canonical_key
            sub_by_key[k2] = sub

    groups: dict[str, list] = {}
    group_meta: dict[str, tuple[MerchantIdentity | None, str, str | None]] = {}

    for tx in expenses:
        cat_rec = cat_map.get(tx.id)
        merchant = merchant_map.get(cat_rec.merchant_id) if (cat_rec and cat_rec.merchant_id) else None
        if merchant is not None:
            key = merchant.canonical_key
            display_name = merchant.normalized_name
        else:
            parsed = normalize_merchant_text(tx.description, tx.merchant_payee)
            key = parsed.canonical_key
            display_name = parsed.normalized_name

        if key == "unknown_merchant":
            continue

        cat_name = (
            (cat_rec.suggested_category_name if cat_rec else None)
            or (tx.category.name if tx.category else None)
        )
        groups.setdefault(key, []).append(tx)
        group_meta[key] = (merchant, display_name, cat_name)

    results: list[RecurringPaymentCandidate] = []
    for key, group_txs in groups.items():
        if len(group_txs) < 2:
            continue

        ordered = sorted(group_txs, key=lambda t: t.transaction_date)
        # Collapse multiple payments on exact same day cleanly for interval checks
        unique_dates: list[dt.date] = []
        for t in ordered:
            if not unique_dates or t.transaction_date != unique_dates[-1]:
                unique_dates.append(t.transaction_date)
        if len(unique_dates) < 2:
            continue

        intervals = [
            (unique_dates[i] - unique_dates[i - 1]).days
            for i in range(1, len(unique_dates))
        ]
        freq_info = _classify_frequency(intervals)
        if freq_info is None:
            continue
        freq, step_days = freq_info

        # Require either >=3 occurrences or monthly/quarterly with tight/reasonable periodicity
        if len(ordered) == 2 and intervals[0] < 20:
            continue

        amounts = [Decimal(t.amount) for t in ordered]
        min_amt = min(amounts)
        max_amt = max(amounts)
        est_amt = Decimal(str(median([float(a) for a in amounts]))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        variability_pct = Decimal("0.00")
        if est_amt > Decimal("0.00"):
            spread = max_amt - min_amt
            variability_pct = ((spread / est_amt) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Reject ultra-erratic non-recurring daily/random merchants (e.g., 4x variability on food)
        merchant_obj, display_name, cat_name = group_meta[key]
        is_utility_or_sub = (cat_name or "").lower() in (_SUBSCRIPTION_CATS | _UTILITY_CATS | _HOUSING_EMI_CATS)
        max_allowed_spread_pct = Decimal("85.00") if is_utility_or_sub else Decimal("35.00")
        if variability_pct > max_allowed_spread_pct and len(ordered) < 3:
            continue
        if variability_pct > Decimal("120.00"):
            continue

        is_variable = variability_pct > Decimal("10.00")
        interval_consistency = 1.0 - min(
            0.5,
            sum(abs(gap - step_days) for gap in intervals) / max(1, len(intervals) * step_days),
        )
        occurrence_bonus = min(0.18, (len(ordered) - 2) * 0.06)
        var_penalty = 0.08 if is_variable else 0.0
        conf_val = max(0.55, min(0.98, 0.72 * interval_consistency + occurrence_bonus + 0.16 - var_penalty))
        confidence = Decimal(str(round(conf_val, 4)))

        matched_sub = sub_by_key.get(key)
        cand = existing_candidates.get((key, freq))
        if cand is None:
            cand = RecurringPaymentCandidate(
                user_id=user_id,
                merchant_key=key,
                frequency=freq,
            )

        cand.merchant_id = merchant_obj.id if merchant_obj else None
        cand.merchant_name = display_name
        cand.suggested_category_name = cat_name
        cand.commitment_type = _commitment_type(cat_name, variability_pct)
        cand.estimated_amount = est_amt
        cand.min_amount = min_amt
        cand.max_amount = max_amt
        cand.amount_variability_pct = variability_pct
        cand.is_variable_amount = is_variable
        cand.occurrence_count = len(ordered)
        cand.first_seen_date = unique_dates[0]
        cand.last_seen_date = unique_dates[-1]
        cand.next_expected_date = _add_frequency(unique_dates[-1], freq, step_days)
        cand.confidence = confidence
        cand.detection_method = "interval_and_variance_v1"
        cand.evidence = {
            "intervals_days": intervals,
            "supporting_transaction_ids": [str(t.id) for t in ordered[-8:]],
            "amounts": [str(t.amount) for t in ordered[-8:]],
        }
        if matched_sub is not None and cand.linked_subscription_id is None:
            cand.linked_subscription_id = matched_sub.id
            if cand.review_status == "pending":
                cand.review_status = "linked"
        cand.updated_at = dt.datetime.now(dt.UTC)
        db.add(cand)
        results.append(cand)

    db.flush()
    return results
