import datetime as dt
import uuid
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intelligence import (
    MerchantIdentity,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.services.ai.merchant_intelligence import normalize_merchant_text


def _mad(values: list[float], med: float) -> float:
    return median([abs(v - med) for v in values])


def _upsert_anomaly(
    db: Session,
    existing_by_key: dict[str, SpendingAnomaly],
    *,
    user_id: uuid.UUID,
    dedupe_key: str,
    transaction_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    category_name: str | None,
    merchant_name: str | None,
    anomaly_type: str,
    observed_amount: Decimal,
    baseline_amount: Decimal,
    deviation_pct: Decimal,
    severity: str,
    confidence: Decimal,
    detection_method: str,
    explanation: str,
    supporting_tx_ids: list[str],
) -> SpendingAnomaly:
    rec = existing_by_key.get(dedupe_key)
    if rec is None:
        rec = SpendingAnomaly(
            user_id=user_id,
            dedupe_key=dedupe_key,
            review_status="open",
        )
        existing_by_key[dedupe_key] = rec

    rec.transaction_id = transaction_id
    rec.category_id = category_id
    rec.category_name = category_name
    rec.merchant_name = merchant_name
    rec.anomaly_type = anomaly_type
    rec.observed_amount = observed_amount.quantize(Decimal("0.01"))
    rec.baseline_amount = baseline_amount.quantize(Decimal("0.01"))
    rec.deviation_pct = deviation_pct.quantize(Decimal("0.01"))
    rec.severity = severity
    rec.confidence = confidence
    rec.detection_method = detection_method
    rec.explanation = explanation
    rec.supporting_transaction_ids = supporting_tx_ids
    db.add(rec)
    return rec


def detect_anomalies_for_user(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    *,
    lookback_days: int = 365,
) -> list[SpendingAnomaly]:
    """
    Detect explainable statistical spending anomalies (never labeled as fraud).
    Preserves existing acknowledged/dismissed review status via dedupe_key.
    """
    since_date = dt.date.today() - dt.timedelta(days=lookback_days)
    txs = repo.list_eligible_transactions(
        db, user_id, date_from=since_date, include_transfers=False
    )
    expenses = [tx for tx in txs if tx.transaction_type == "expense"]
    if not expenses:
        return []

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
    existing_by_key = {
        a.dedupe_key: a
        for a in db.execute(
            select(SpendingAnomaly).where(SpendingAnomaly.user_id == user_id)
        )
        .scalars()
        .all()
    }

    by_category: dict[str, list] = {}
    by_merchant_key: dict[str, list] = {}
    cat_monthly: dict[tuple[str, str], dict] = {}

    for tx in expenses:
        cat_rec = cat_map.get(tx.id)
        cat_id = tx.category_id or (cat_rec.suggested_category_id if cat_rec else None)
        cat_name = (
            (tx.category.name if tx.category else None)
            or (cat_rec.suggested_category_name if cat_rec else None)
            or "Uncategorized"
        )
        m_obj = merchant_map.get(cat_rec.merchant_id) if (cat_rec and cat_rec.merchant_id) else None
        if m_obj is not None:
            m_key = m_obj.canonical_key
            m_name = m_obj.normalized_name
        else:
            parsed = normalize_merchant_text(tx.description, tx.merchant_payee)
            m_key = parsed.canonical_key
            m_name = parsed.normalized_name

        by_category.setdefault(cat_name, []).append((tx, cat_id, m_name))
        if m_key != "unknown_merchant":
            by_merchant_key.setdefault(m_key, []).append((tx, cat_id, cat_name, m_name))

        month_str = tx.transaction_date.strftime("%Y-%m")
        cm = cat_monthly.setdefault(
            (cat_name, month_str),
            {"total": Decimal("0.00"), "cat_id": cat_id, "tx_ids": []},
        )
        cm["total"] += Decimal(tx.amount)
        cm["tx_ids"].append(str(tx.id))

    detected: list[SpendingAnomaly] = []

    # 1. Single-transaction outlier within category (Median + MAD)
    for cat_name, entries in by_category.items():
        if len(entries) < 4:
            continue
        amounts = [float(item[0].amount) for item in entries]
        med = median(amounts)
        if med <= 0:
            continue
        mad_val = _mad(amounts, med)
        for tx, cat_id, m_name in entries:
            obs = float(tx.amount)
            diff = obs - med
            if diff < 500.0:
                continue
            mod_z = (0.6745 * diff / mad_val) if mad_val > 0 else (obs / med)
            ratio = obs / med
            if (mad_val > 0 and mod_z >= 3.5 and ratio >= 2.0) or (mad_val == 0 and ratio >= 2.5):
                dev_pct = Decimal(str(round(((obs - med) / med) * 100.0, 2)))
                sev = "high" if ratio >= 4.0 else ("medium" if ratio >= 2.5 else "low")
                conf = Decimal(str(round(min(0.96, 0.68 + min(0.25, mod_z / 25.0)), 4)))
                detected.append(
                    _upsert_anomaly(
                        db,
                        existing_by_key,
                        user_id=user_id,
                        dedupe_key=f"tx_cat_spike:{tx.id}",
                        transaction_id=tx.id,
                        category_id=cat_id,
                        category_name=cat_name,
                        merchant_name=m_name,
                        anomaly_type="category_transaction_spike",
                        observed_amount=Decimal(tx.amount),
                        baseline_amount=Decimal(str(round(med, 2))),
                        deviation_pct=dev_pct,
                        severity=sev,
                        confidence=conf,
                        detection_method="robust_median_mad",
                        explanation=(
                            f"Expense of INR {tx.amount:,.2f} at {m_name} is {ratio:.1f}x your typical "
                            f"'{cat_name}' median of INR {med:,.2f} across {len(entries)} transactions."
                        ),
                        supporting_tx_ids=[str(tx.id)],
                    )
                )

    # 2. Category monthly spike
    months_by_cat: dict[str, list[tuple[str, Decimal, uuid.UUID | None, list[str]]]] = {}
    for (cat_name, month_str), bucket in cat_monthly.items():
        months_by_cat.setdefault(cat_name, []).append(
            (month_str, bucket["total"], bucket["cat_id"], bucket["tx_ids"])
        )

    for cat_name, m_list in months_by_cat.items():
        if len(m_list) < 3:
            continue
        ordered_months = sorted(m_list, key=lambda x: x[0])
        latest_m, latest_tot, latest_cat_id, latest_tx_ids = ordered_months[-1]
        prior_totals = [float(x[1]) for x in ordered_months[:-1]]
        prior_med = median(prior_totals)
        if prior_med <= 0:
            continue
        obs = float(latest_tot)
        if (obs - prior_med) >= 1000.0 and obs >= prior_med * 1.65:
            dev_pct = Decimal(str(round(((obs - prior_med) / prior_med) * 100.0, 2)))
            sev = "high" if obs >= prior_med * 2.5 else "medium"
            detected.append(
                _upsert_anomaly(
                    db,
                    existing_by_key,
                    user_id=user_id,
                    dedupe_key=f"cat_month_spike:{cat_name}:{latest_m}",
                    transaction_id=None,
                    category_id=latest_cat_id,
                    category_name=cat_name,
                    merchant_name=None,
                    anomaly_type="category_monthly_spike",
                    observed_amount=latest_tot,
                    baseline_amount=Decimal(str(round(prior_med, 2))),
                    deviation_pct=dev_pct,
                    severity=sev,
                    confidence=Decimal("0.8400"),
                    detection_method="monthly_baseline_comparison",
                    explanation=(
                        f"Your '{cat_name}' spending in {latest_m} (INR {latest_tot:,.2f}) exceeded your "
                        f"prior monthly median (INR {prior_med:,.2f}) by {dev_pct}%."
                    ),
                    supporting_tx_ids=latest_tx_ids[-8:],
                )
            )

    # 3. Recurring payment jump / price hike
    recur_cands = db.execute(
        select(RecurringPaymentCandidate).where(
            RecurringPaymentCandidate.user_id == user_id,
            RecurringPaymentCandidate.review_status != "rejected",
        )
    ).scalars().all()
    for rc in recur_cands:
        entries = by_merchant_key.get(rc.merchant_key, [])
        if len(entries) < 3:
            continue
        ordered = sorted(entries, key=lambda item: item[0].transaction_date)
        latest_tx, cat_id, cat_name, m_name = ordered[-1]
        prior_vals = [float(item[0].amount) for item in ordered[:-1]]
        base_med = median(prior_vals)
        obs = float(latest_tx.amount)
        if base_med > 0 and (obs - base_med) >= 100.0 and obs >= base_med * 1.20:
            dev_pct = Decimal(str(round(((obs - base_med) / base_med) * 100.0, 2)))
            sev = "high" if obs >= base_med * 1.50 else "medium"
            detected.append(
                _upsert_anomaly(
                    db,
                    existing_by_key,
                    user_id=user_id,
                    dedupe_key=f"recur_jump:{rc.merchant_key}:{latest_tx.id}",
                    transaction_id=latest_tx.id,
                    category_id=cat_id,
                    category_name=cat_name,
                    merchant_name=m_name,
                    anomaly_type="recurring_amount_jump",
                    observed_amount=Decimal(latest_tx.amount),
                    baseline_amount=Decimal(str(round(base_med, 2))),
                    deviation_pct=dev_pct,
                    severity=sev,
                    confidence=Decimal("0.8800"),
                    detection_method="recurring_charge_delta",
                    explanation=(
                        f"Recurring payment to {m_name} increased to INR {latest_tx.amount:,.2f} "
                        f"(+{dev_pct}% vs prior median of INR {base_med:,.2f})."
                    ),
                    supporting_tx_ids=[str(item[0].id) for item in ordered[-4:]],
                )
            )

    db.flush()
    return detected
