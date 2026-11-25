import datetime as dt
import re
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from app.models.finance import FinancialTransaction
from app.models.subscriptions import Subscription, SubscriptionCandidateDecision
from app.schemas.subscriptions import SubscriptionCandidateResponse
from app.services.bills.recurrence import advance_due_date

TWO_DP = Decimal("0.01")

NON_SUBSCRIPTION_PATTERN = re.compile(
    r"\b("
    r"electricity|water\s+tax|bwssb|bescom|msedcl|tata\s+power|adani\s+electricity|"
    r"gas|indane|hp\s+gas|mahanagar\s+gas|emi|loan|mortgage|home\s+loan|car\s+loan|"
    r"house\s+rent|rent|maintenance|society|insurance|lic|hdfc\s+life|icici\s+pru|"
    r"property\s+tax|broadband\s+bill"
    r")\b",
    re.IGNORECASE,
)


def quantize_inr(val: Decimal) -> Decimal:
    return val.quantize(TWO_DP, rounding=ROUND_HALF_UP)


def compute_monthly_and_annual_equivalent(
    amount: Decimal | None,
    frequency: str,
    custom_interval_days: int | None = None,
) -> tuple[Decimal | None, Decimal | None]:
    """
    Normalizes a subscription price to estimated monthly & annual recurring equivalents
    using exact Decimal math. Missing prices remain None.
    """
    if amount is None:
        return None, None
    amt = Decimal(amount)
    if frequency == "weekly":
        annual = quantize_inr(amt * Decimal("52"))
        monthly = quantize_inr((amt * Decimal("52")) / Decimal("12"))
        return monthly, annual
    if frequency == "monthly":
        return quantize_inr(amt), quantize_inr(amt * Decimal("12"))
    if frequency == "quarterly":
        return quantize_inr(amt / Decimal("3")), quantize_inr(amt * Decimal("4"))
    if frequency == "half_yearly":
        return quantize_inr(amt / Decimal("6")), quantize_inr(amt * Decimal("2"))
    if frequency == "yearly":
        return quantize_inr(amt / Decimal("12")), quantize_inr(amt)
    if frequency == "custom" and custom_interval_days and custom_interval_days > 0:
        days = Decimal(custom_interval_days)
        monthly = quantize_inr((amt * Decimal("30")) / days)
        annual = quantize_inr((amt * Decimal("365")) / days)
        return monthly, annual
    return quantize_inr(amt), quantize_inr(amt * Decimal("12"))


def advance_subscription_renewal(
    current_date: dt.date,
    frequency: str,
    anchor_day: int,
    custom_interval_days: int | None = None,
) -> dt.date:
    return advance_due_date(
        current_due=current_date,
        frequency=frequency,
        anchor_day=anchor_day,
        custom_interval_days=custom_interval_days,
    )


def _normalize_merchant_token(tx: FinancialTransaction) -> tuple[str, str]:
    raw = (tx.merchant_payee or tx.description or "").strip()
    lower = raw.lower()
    lower = re.sub(r"\b(upi|imps|neft|pos|ach|autopay|mandate|si|ref|tx|txn)\b", " ", lower)
    lower = re.sub(r"[0-9_\-/#*]+", " ", lower)
    lower = re.sub(r"\s+", " ", lower).strip()
    key = re.sub(r"[^a-z]+", "", lower)[:40]
    display = raw[:80] if raw else lower.title()
    return key, display


def _classify_interval(avg_days: float) -> str | None:
    if 5.5 <= avg_days <= 8.5:
        return "weekly"
    if 26 <= avg_days <= 34:
        return "monthly"
    if 85 <= avg_days <= 96:
        return "quarterly"
    if 175 <= avg_days <= 190:
        return "half_yearly"
    if 355 <= avg_days <= 375:
        return "yearly"
    return None


def detect_subscription_candidates(
    expense_txs: list[FinancialTransaction],
    existing_subs: list[Subscription],
    already_linked_tx_ids: set[uuid.UUID],
    decisions: dict[str, SubscriptionCandidateDecision],
) -> list[SubscriptionCandidateResponse]:
    """
    Deterministic recurring subscription candidate detection from historical expense transactions.
    Never creates subscriptions automatically; excludes known bills/EMIs/utility descriptions,
    non-recurring variance, and previously ignored/linked merchants.
    """
    existing_keys: set[str] = set()
    for sub in existing_subs:
        if sub.status in {"archived"}:
            continue
        for label in (sub.subscription_name, sub.provider_name):
            if label:
                existing_keys.add(re.sub(r"[^a-z]+", "", label.lower())[:40])

    grouped: dict[str, list[FinancialTransaction]] = defaultdict(list)
    display_map: dict[str, str] = {}

    for tx in expense_txs:
        if tx.id in already_linked_tx_ids:
            continue
        if tx.source in {"bill_payment", "subscription_payment", "loan_payment"}:
            continue
        full_text = f"{tx.merchant_payee or ''} {tx.description or ''}"
        if NON_SUBSCRIPTION_PATTERN.search(full_text):
            continue

        key, disp = _normalize_merchant_token(tx)
        if len(key) < 3:
            continue
        if key in decisions:
            continue
        if any(ek and (ek in key or key in ek) for ek in existing_keys):
            continue

        grouped[key].append(tx)
        if key not in display_map:
            display_map[key] = disp

    candidates: list[SubscriptionCandidateResponse] = []
    for key, txs in grouped.items():
        if len(txs) < 2:
            continue
        txs_sorted = sorted(txs, key=lambda t: t.transaction_date)
        amounts = [Decimal(t.amount) for t in txs_sorted]
        min_amt, max_amt = min(amounts), max(amounts)
        if min_amt <= Decimal("0.00"):
            continue
        # Require consistent amount (max within 10% of min)
        if max_amt > (min_amt * Decimal("1.10")):
            continue

        gaps = [
            (txs_sorted[i].transaction_date - txs_sorted[i - 1].transaction_date).days
            for i in range(1, len(txs_sorted))
        ]
        if any(g < 5 for g in gaps):
            continue
        avg_gap = sum(gaps) / len(gaps)
        freq = _classify_interval(avg_gap)
        if not freq:
            continue

        last_tx = txs_sorted[-1]
        next_est = advance_subscription_renewal(
            last_tx.transaction_date, freq, anchor_day=txs_sorted[0].transaction_date.day
        )
        candidates.append(
            SubscriptionCandidateResponse(
                merchant_key=key,
                display_name=display_map[key],
                estimated_amount=quantize_inr(last_tx.amount),
                detected_frequency=freq,
                occurrence_count=len(txs_sorted),
                first_seen=txs_sorted[0].transaction_date,
                last_seen=last_tx.transaction_date,
                suggested_next_date=next_est,
                sample_transaction_ids=[t.id for t in txs_sorted[-5:]],
                confidence_note=(
                    f"{len(txs_sorted)} consistent ~₹{last_tx.amount:,.2f} charges spaced "
                    f"~{round(avg_gap)} days apart ({freq})."
                ),
            )
        )

    candidates.sort(key=lambda c: c.last_seen, reverse=True)
    return candidates
