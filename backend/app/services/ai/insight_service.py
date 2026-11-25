import datetime as dt
import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intelligence import (
    FinancialInsight,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.intelligence import SpendingPatternsResponse
from app.services.ai.ai_provider import AiProvider, InsightNarrativeAiInput, NullAiProvider


def _upsert_insight(
    db: Session,
    existing_by_key: dict[str, FinancialInsight],
    *,
    user_id: uuid.UUID,
    dedupe_key: str,
    insight_type: str,
    title: str,
    description: str,
    severity: str,
    period_start: dt.date,
    period_end: dt.date,
    supporting_data: dict,
    calculation_method: str,
    confidence: Decimal,
    suggested_action: str | None,
    provider: AiProvider,
    enrich_with_ai: bool,
) -> FinancialInsight:
    rec = existing_by_key.get(dedupe_key)
    final_title = title
    final_desc = description
    final_action = suggested_action
    provider_used = "local"

    already_enriched = (
        rec is not None
        and provider.is_available()
        and rec.provider_name == provider.provider_name
    )
    if already_enriched and rec is not None:
        final_title = rec.title
        final_desc = rec.description
        final_action = rec.suggested_action or suggested_action
        provider_used = rec.provider_name or provider.provider_name
    elif enrich_with_ai and provider.is_available():
        enriched = provider.enrich_insight_narrative(
            InsightNarrativeAiInput(
                insight_type=insight_type,
                base_title=title,
                base_description=description,
                base_action=suggested_action,
                supporting_metrics=supporting_data,
            )
        )
        if enriched is not None:
            final_title = enriched.title
            final_desc = enriched.description
            final_action = enriched.suggested_action or suggested_action
            provider_used = provider.provider_name

    if rec is None:
        rec = FinancialInsight(
            user_id=user_id,
            dedupe_key=dedupe_key,
            status="new",
        )
        existing_by_key[dedupe_key] = rec

    rec.insight_type = insight_type
    rec.title = final_title
    rec.description = final_desc
    rec.severity = severity
    rec.period_start = period_start
    rec.period_end = period_end
    rec.supporting_data = supporting_data
    rec.calculation_method = calculation_method
    rec.provider_name = provider_used
    rec.confidence = confidence
    rec.suggested_action = final_action
    rec.generated_at = dt.datetime.now(dt.UTC)
    db.add(rec)
    return rec


def generate_insights_for_user(
    db: Session,
    repo: IntelligenceRepository,
    user_id: uuid.UUID,
    patterns: SpendingPatternsResponse,
    *,
    ai_provider: AiProvider | None = None,
    use_ai_enrichment: bool = True,
) -> list[FinancialInsight]:
    """
    Generate structured, evidence-backed financial insights strictly from verified user data.
    Never creates fake savings claims or unverified forecasts.
    """
    provider = ai_provider or NullAiProvider()
    existing_by_key = {
        ins.dedupe_key: ins
        for ins in db.execute(
            select(FinancialInsight).where(FinancialInsight.user_id == user_id)
        )
        .scalars()
        .all()
    }

    insights: list[FinancialInsight] = []
    if patterns.total_expense <= Decimal("0.00"):
        return insights

    period_key = f"{patterns.period_start.isoformat()}:{patterns.period_end.isoformat()}"

    # 1. Essential vs Discretionary balance
    disc_pct = (
        (patterns.discretionary_total / patterns.total_expense) * Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if disc_pct >= Decimal("40.00"):
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"discretionary_share:{period_key}",
                insight_type="spending_mix",
                title=f"Discretionary spending accounts for {disc_pct}% of outflows",
                description=(
                    f"Between {patterns.period_start} and {patterns.period_end}, discretionary categories "
                    f"totaled INR {patterns.discretionary_total:,.2f} out of INR {patterns.total_expense:,.2f} total expenses."
                ),
                severity="medium" if disc_pct >= Decimal("55.00") else "info",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={
                    "discretionary_total": str(patterns.discretionary_total),
                    "essential_total": str(patterns.essential_total),
                    "total_expense": str(patterns.total_expense),
                    "discretionary_pct": str(disc_pct),
                },
                calculation_method="essential_vs_discretionary_ratio",
                confidence=Decimal("0.9200"),
                suggested_action="Review top discretionary categories to identify optional cutbacks.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    # 2. Month-over-Month surge check
    if len(patterns.monthly_trend) >= 2:
        prev_m = patterns.monthly_trend[-2]
        curr_m = patterns.monthly_trend[-1]
        if prev_m.total_expense > Decimal("0.00"):
            delta = curr_m.total_expense - prev_m.total_expense
            pct_chg = ((delta / prev_m.total_expense) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if delta >= Decimal("500.00") and pct_chg >= Decimal("15.00"):
                insights.append(
                    _upsert_insight(
                        db,
                        existing_by_key,
                        user_id=user_id,
                        dedupe_key=f"mom_surge:{curr_m.month}",
                        insight_type="monthly_comparison",
                        title=f"{curr_m.month} spending rose {pct_chg}% vs {prev_m.month}",
                        description=(
                            f"Outflows moved from INR {prev_m.total_expense:,.2f} in {prev_m.month} to "
                            f"INR {curr_m.total_expense:,.2f} in {curr_m.month} (+INR {delta:,.2f})."
                        ),
                        severity="warning" if pct_chg >= Decimal("30.00") else "medium",
                        period_start=patterns.period_start,
                        period_end=patterns.period_end,
                        supporting_data={
                            "previous_month": prev_m.month,
                            "previous_expense": str(prev_m.total_expense),
                            "current_month": curr_m.month,
                            "current_expense": str(curr_m.total_expense),
                            "change_pct": str(pct_chg),
                        },
                        calculation_method="mom_expense_delta",
                        confidence=Decimal("0.9500"),
                        suggested_action="Inspect the latest month's category & anomaly breakdown.",
                        provider=provider,
                        enrich_with_ai=use_ai_enrichment,
                    )
                )

    # 3. Recurring burden insight
    pending_recur = db.execute(
        select(RecurringPaymentCandidate).where(
            RecurringPaymentCandidate.user_id == user_id,
            RecurringPaymentCandidate.review_status == "pending",
        )
    ).scalars().all()
    if patterns.recurring_total > Decimal("0.00") or pending_recur:
        recur_share = (
            (patterns.recurring_total / patterns.total_expense) * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"recurring_commitments:{period_key}",
                insight_type="recurring_commitments",
                title=f"Recurring commitments represent {recur_share}% of spending",
                description=(
                    f"Recurring expenses totaled INR {patterns.recurring_total:,.2f} "
                    f"across the period, with {len(pending_recur)} detected recurring series pending confirmation."
                ),
                severity="info",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={
                    "recurring_total": str(patterns.recurring_total),
                    "recurring_share_pct": str(recur_share),
                    "pending_candidates": len(pending_recur),
                },
                calculation_method="recurring_expense_ratio",
                confidence=Decimal("0.9000"),
                suggested_action="Confirm or link pending recurring candidates in the Recurring Payments tab.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    # 4. Weekend concentration insight
    if patterns.weekend_share_pct >= Decimal("35.00"):
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"weekend_skew:{period_key}",
                insight_type="behaviour_pattern",
                title=f"Weekend spending accounts for {patterns.weekend_share_pct}% of expenses",
                description=(
                    f"Saturday & Sunday expenses totaled INR {patterns.weekend_expense:,.2f} vs "
                    f"INR {patterns.weekday_expense:,.2f} on weekdays."
                ),
                severity="info",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={
                    "weekend_expense": str(patterns.weekend_expense),
                    "weekday_expense": str(patterns.weekday_expense),
                    "weekend_share_pct": str(patterns.weekend_share_pct),
                },
                calculation_method="weekend_vs_weekday_split",
                confidence=Decimal("0.9300"),
                suggested_action="Monitor weekend dining and shopping transactions if targeting savings.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    # 5. Merchant concentration insight
    if patterns.top_3_merchant_concentration_pct >= Decimal("45.00") and patterns.by_merchant:
        top_names = [m.label for m in patterns.by_merchant[:3]]
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"merchant_conc:{period_key}",
                insight_type="merchant_concentration",
                title=f"Top 3 merchants account for {patterns.top_3_merchant_concentration_pct}% of spend",
                description=(
                    f"Your top merchants ({', '.join(top_names)}) captured "
                    f"{patterns.top_3_merchant_concentration_pct}% of period outflows."
                ),
                severity="info",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={
                    "top_merchants": top_names,
                    "top_3_concentration_pct": str(patterns.top_3_merchant_concentration_pct),
                },
                calculation_method="top3_merchant_concentration",
                confidence=Decimal("0.9400"),
                suggested_action="Check Merchant Intelligence to ensure default categories are mapped cleanly.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    # 6. Open anomaly & review backlog alerts
    open_anoms = db.execute(
        select(SpendingAnomaly).where(
            SpendingAnomaly.user_id == user_id,
            SpendingAnomaly.review_status == "open",
        )
    ).scalars().all()
    if open_anoms:
        high_cnt = sum(1 for a in open_anoms if a.severity == "high")
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"open_anomalies:{dt.date.today().strftime('%Y-%m')}",
                insight_type="anomaly_alert",
                title=f"{len(open_anoms)} statistical spending anomal{'y' if len(open_anoms) == 1 else 'ies'} awaiting review",
                description=(
                    f"Detected {len(open_anoms)} open unusual spend deviations ({high_cnt} high severity) "
                    "compared against your historical category and recurring baselines."
                ),
                severity="warning" if high_cnt > 0 else "medium",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={"open_count": len(open_anoms), "high_severity_count": high_cnt},
                calculation_method="open_anomaly_count",
                confidence=Decimal("0.9600"),
                suggested_action="Review and acknowledge or dismiss anomalies in the Anomalies tab.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    needs_review_cnt = len(
        db.execute(
            select(TransactionCategorization.id).where(
                TransactionCategorization.user_id == user_id,
                TransactionCategorization.review_status == "needs_review",
            )
        )
        .scalars()
        .all()
    )
    if needs_review_cnt >= 3:
        insights.append(
            _upsert_insight(
                db,
                existing_by_key,
                user_id=user_id,
                dedupe_key=f"review_backlog:{dt.date.today().strftime('%Y-%m')}",
                insight_type="data_quality",
                title=f"{needs_review_cnt} transactions need category confirmation",
                description=(
                    f"Confirming or overriding {needs_review_cnt} flagged transactions will improve your personal "
                    "TF-IDF classifier accuracy and merchant category mappings."
                ),
                severity="info",
                period_start=patterns.period_start,
                period_end=patterns.period_end,
                supporting_data={"needs_review_count": needs_review_cnt},
                calculation_method="needs_review_queue_size",
                confidence=Decimal("0.9800"),
                suggested_action="Confirm suggested categories in Transaction Intelligence.",
                provider=provider,
                enrich_with_ai=use_ai_enrichment,
            )
        )

    db.flush()
    return insights
