import datetime as dt
import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.finance import FinancialTransaction
from app.models.intelligence import (
    AiModelMetadata,
    AiProcessingJob,
    CategorizationFeedback,
    FinancialInsight,
    MerchantCategoryMapping,
    MerchantIdentity,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)
from app.models.subscriptions import Subscription
from app.models.user import User
from app.repositories.intelligence.intelligence_repository import IntelligenceRepository
from app.schemas.intelligence import (
    AiModelMetadataResponse,
    AiProcessingJobResponse,
    AnomalyReviewRequest,
    CategorizationFeedbackResponse,
    CategorizeTransactionsRequest,
    CategorySummaryItem,
    FinancialInsightListResponse,
    FinancialInsightResponse,
    InsightReviewRequest,
    IntelligenceOverviewResponse,
    IntelligenceRunRequest,
    MerchantIdentityResponse,
    MerchantListResponse,
    MerchantUpdateRequest,
    OverviewMetricCard,
    RecurringCandidateDecisionRequest,
    RecurringCandidateListResponse,
    RecurringPaymentCandidateResponse,
    SpendingAnomalyListResponse,
    SpendingAnomalyResponse,
    SpendingPatternsResponse,
    TransactionCategorizationListResponse,
    TransactionCategorizationOverrideRequest,
    TransactionCategorizationResponse,
)
from app.services.ai.ai_provider import AiProvider
from app.services.ai.anomaly_service import detect_anomalies_for_user
from app.services.ai.categorization_service import run_categorization_for_user
from app.services.ai.groq_provider import PROMPT_VERSION_CATEGORIZATION, get_ai_provider
from app.services.ai.insight_service import generate_insights_for_user
from app.services.ai.ml_classifier import train_and_evaluate_user_classifier
from app.services.ai.pattern_service import compute_spending_patterns
from app.services.ai.recurring_intelligence import detect_recurring_payments_for_user
from app.services.finance.category_service import CategoryService


class IntelligenceService:
    """Orchestrator service for Phase 8 AI Expense Intelligence."""

    def __init__(self):
        self.repo = IntelligenceRepository()

    def _ensure_categories_ready(self, db: Session) -> None:
        CategoryService().seed_default_categories(db, commit=False)

    def _serialize_tx_categorization(
        self,
        rec: TransactionCategorization,
        tx: FinancialTransaction,
        merchant: MerchantIdentity | None,
    ) -> TransactionCategorizationResponse:
        return TransactionCategorizationResponse(
            id=rec.id,
            transaction_id=rec.transaction_id,
            merchant_id=rec.merchant_id,
            transaction_date=tx.transaction_date,
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            currency=tx.currency,
            description=tx.description,
            merchant_payee=tx.merchant_payee,
            normalized_merchant_name=merchant.normalized_name if merchant else None,
            current_category_id=rec.current_category_id,
            current_category_name=rec.current_category_name,
            suggested_category_id=rec.suggested_category_id,
            suggested_category_name=rec.suggested_category_name,
            predicted_category_name=rec.predicted_category_name,
            classification_method=rec.classification_method,
            confidence=rec.confidence,
            explanation=rec.explanation,
            evidence=rec.evidence or {},
            model_version=rec.model_version,
            provider_name=rec.provider_name,
            review_status=rec.review_status,
            analyzed_at=rec.analyzed_at,
            updated_at=rec.updated_at,
        )

    def get_overview(
        self, db: Session, user: User, *, lookback_days: int = 180
    ) -> IntelligenceOverviewResponse:
        eligible_txs = self.repo.list_eligible_transactions(db, user.id, include_transfers=False)
        analyzed_cnt = db.execute(
            select(func.count(TransactionCategorization.id)).where(
                TransactionCategorization.user_id == user.id
            )
        ).scalar_one()
        needs_review_cnt = db.execute(
            select(func.count(TransactionCategorization.id)).where(
                TransactionCategorization.user_id == user.id,
                TransactionCategorization.review_status == "needs_review",
            )
        ).scalar_one()
        confirmed_cnt = db.execute(
            select(func.count(TransactionCategorization.id)).where(
                TransactionCategorization.user_id == user.id,
                TransactionCategorization.review_status.in_(["confirmed", "overridden"]),
            )
        ).scalar_one()
        merchant_cnt = db.execute(
            select(func.count(MerchantIdentity.id)).where(MerchantIdentity.user_id == user.id)
        ).scalar_one()
        recur_cnt = db.execute(
            select(func.count(RecurringPaymentCandidate.id)).where(
                RecurringPaymentCandidate.user_id == user.id
            )
        ).scalar_one()
        pending_recur_cnt = db.execute(
            select(func.count(RecurringPaymentCandidate.id)).where(
                RecurringPaymentCandidate.user_id == user.id,
                RecurringPaymentCandidate.review_status == "pending",
            )
        ).scalar_one()
        open_anom_cnt = db.execute(
            select(func.count(SpendingAnomaly.id)).where(
                SpendingAnomaly.user_id == user.id,
                SpendingAnomaly.review_status == "open",
            )
        ).scalar_one()
        high_anom_cnt = db.execute(
            select(func.count(SpendingAnomaly.id)).where(
                SpendingAnomaly.user_id == user.id,
                SpendingAnomaly.review_status == "open",
                SpendingAnomaly.severity == "high",
            )
        ).scalar_one()
        unread_ins_cnt = db.execute(
            select(func.count(FinancialInsight.id)).where(
                FinancialInsight.user_id == user.id,
                FinancialInsight.status == "new",
            )
        ).scalar_one()
        total_ins_cnt = db.execute(
            select(func.count(FinancialInsight.id)).where(
                FinancialInsight.user_id == user.id,
                FinancialInsight.status != "dismissed",
            )
        ).scalar_one()

        model_meta = self.repo.get_model_metadata(db, user.id)
        jobs = self.repo.list_jobs(db, user.id, limit=5)
        last_job = jobs[0] if jobs else None

        end_d = dt.date.today()
        start_d = end_d - dt.timedelta(days=lookback_days)
        patterns = compute_spending_patterns(
            db, self.repo, user.id, date_from=start_d, date_to=end_d
        )
        top_cats = [
            CategorySummaryItem(
                category_name=item.label,
                transaction_count=item.transaction_count,
                total_amount=item.amount,
                share_pct=item.share_pct,
            )
            for item in patterns.by_category[:6]
        ]

        top_anomalies = [
            SpendingAnomalyResponse.model_validate(a)
            for a in self.repo.list_anomalies(db, user.id, review_status="open", limit=5)
        ]
        top_insights = [
            FinancialInsightResponse.model_validate(i)
            for i in self.repo.list_insights(db, user.id, limit=5)
            if i.status != "dismissed"
        ]

        provider = get_ai_provider()
        metrics = OverviewMetricCard(
            total_analyzed_transactions=analyzed_cnt,
            total_eligible_transactions=len(eligible_txs),
            needs_review_count=needs_review_cnt,
            confirmed_count=confirmed_cnt,
            merchant_count=merchant_cnt,
            recurring_candidate_count=recur_cnt,
            pending_recurring_count=pending_recur_cnt,
            open_anomaly_count=open_anom_cnt,
            high_severity_anomaly_count=high_anom_cnt,
            unread_insight_count=unread_ins_cnt,
            total_insight_count=total_ins_cnt,
            ml_model_status=model_meta.status if model_meta else "untrained",
            ml_model_version=model_meta.model_version if model_meta else None,
            ml_training_samples=model_meta.training_sample_count if model_meta else 0,
            groq_enabled=provider.is_available(),
            groq_model=settings.GROQ_MODEL,
            last_job_status=last_job.status if last_job else None,
            last_job_completed_at=last_job.completed_at if last_job else None,
        )

        return IntelligenceOverviewResponse(
            metrics=metrics,
            model_metadata=AiModelMetadataResponse.model_validate(model_meta) if model_meta else None,
            recent_jobs=[AiProcessingJobResponse.model_validate(j) for j in jobs],
            top_categories=top_cats,
            top_anomalies=top_anomalies,
            top_insights=top_insights,
        )

    def enqueue_intelligence_job(
        self, db: Session, user: User, *, job_type: str = "full_intelligence"
    ) -> AiProcessingJob:
        existing = self.repo.get_active_job(db, user.id, job_type)
        if existing is not None:
            return existing
        provider = get_ai_provider()
        job = AiProcessingJob(
            user_id=user.id,
            job_type=job_type,
            status="queued",
            provider_name=provider.provider_name if provider.is_available() else "local",
            model_name=provider.model_name if provider.is_available() else "deterministic+sklearn",
            prompt_version=PROMPT_VERSION_CATEGORIZATION,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    def execute_full_pipeline_for_user(
        self,
        db: Session,
        user_id: uuid.UUID,
        req: IntelligenceRunRequest,
        *,
        ai_provider: AiProvider | None = None,
        existing_job: AiProcessingJob | None = None,
    ) -> AiProcessingJob:
        self._ensure_categories_ready(db)
        provider = ai_provider or get_ai_provider()

        job = existing_job
        if job is None:
            job = AiProcessingJob(
                user_id=user_id,
                job_type="full_intelligence",
                status="processing",
                provider_name=provider.provider_name if (req.use_ai_fallback and provider.is_available()) else "local",
                model_name=provider.model_name if (req.use_ai_fallback and provider.is_available()) else "deterministic+sklearn",
                prompt_version=PROMPT_VERSION_CATEGORIZATION,
                attempt_count=1,
                started_at=dt.datetime.now(dt.UTC),
            )
            db.add(job)
            db.flush()

        try:
            model_meta: AiModelMetadata | None = None
            if req.train_model:
                model_meta = train_and_evaluate_user_classifier(db, self.repo, user_id)

            cat_out = run_categorization_for_user(
                db,
                self.repo,
                user_id,
                reanalyze_all=req.reanalyze_all,
                use_ai_fallback=req.use_ai_fallback,
                ai_provider=provider,
            )

            recur_cands = detect_recurring_payments_for_user(
                db, self.repo, user_id, lookback_days=max(365, req.lookback_days)
            )
            anomalies = detect_anomalies_for_user(
                db, self.repo, user_id, lookback_days=req.lookback_days
            )
            end_d = dt.date.today()
            start_d = end_d - dt.timedelta(days=req.lookback_days)
            patterns = compute_spending_patterns(
                db, self.repo, user_id, date_from=start_d, date_to=end_d
            )
            insights = generate_insights_for_user(
                db,
                self.repo,
                user_id,
                patterns,
                ai_provider=provider,
                use_ai_enrichment=req.use_ai_fallback,
            )

            job.status = "completed"
            job.items_processed = cat_out.processed
            job.summary = {
                "categorized_processed": cat_out.processed,
                "needs_review": cat_out.needs_review,
                "auto_categorized": cat_out.auto_categorized,
                "rule_matched": cat_out.rule_matched,
                "ml_matched": cat_out.ml_matched,
                "llm_matched": cat_out.llm_matched,
                "llm_calls": cat_out.llm_calls,
                "ml_status": model_meta.status if model_meta else "skipped",
                "recurring_candidates_detected": len(recur_cands),
                "anomalies_detected": len(anomalies),
                "insights_generated": len(insights),
            }
            job.completed_at = dt.datetime.now(dt.UTC)
            db.add(job)
            db.commit()
            db.refresh(job)
            return job
        except Exception as exc:
            db.rollback()
            if existing_job is not None:
                job_ref = db.get(AiProcessingJob, existing_job.id)
                if job_ref:
                    job_ref.status = "failed"
                    job_ref.error_message = str(exc)[:500]
                    job_ref.completed_at = dt.datetime.now(dt.UTC)
                    db.add(job_ref)
                    db.commit()
            raise

    def run_categorization(
        self,
        db: Session,
        user: User,
        req: CategorizeTransactionsRequest,
        *,
        ai_provider: AiProvider | None = None,
    ) -> dict:
        self._ensure_categories_ready(db)
        provider = ai_provider or get_ai_provider()
        out = run_categorization_for_user(
            db,
            self.repo,
            user.id,
            tx_ids=req.transaction_ids,
            reanalyze_all=req.reanalyze_all,
            use_ai_fallback=req.use_ai_fallback,
            ai_provider=provider,
        )
        db.commit()
        return {
            "processed": out.processed,
            "needs_review": out.needs_review,
            "auto_categorized": out.auto_categorized,
            "rule_matched": out.rule_matched,
            "ml_matched": out.ml_matched,
            "llm_matched": out.llm_matched,
            "user_preserved": out.user_preserved,
            "llm_calls": out.llm_calls,
        }

    def train_classifier(self, db: Session, user: User) -> AiModelMetadataResponse:
        self._ensure_categories_ready(db)
        meta = train_and_evaluate_user_classifier(db, self.repo, user.id)
        db.commit()
        db.refresh(meta)
        return AiModelMetadataResponse.model_validate(meta)

    def get_model_status(self, db: Session, user: User) -> AiModelMetadataResponse | None:
        meta = self.repo.get_model_metadata(db, user.id)
        return AiModelMetadataResponse.model_validate(meta) if meta else None

    def list_categorizations(
        self,
        db: Session,
        user: User,
        *,
        review_status: str | None = None,
        method: str | None = None,
        search: str | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> TransactionCategorizationListResponse:
        rows, total = self.repo.list_categorizations(
            db,
            user.id,
            review_status=review_status,
            method=method,
            search=search,
            min_confidence=min_confidence,
            max_confidence=max_confidence,
            page=page,
            page_size=page_size,
        )
        needs_review_cnt = db.execute(
            select(func.count(TransactionCategorization.id)).where(
                TransactionCategorization.user_id == user.id,
                TransactionCategorization.review_status == "needs_review",
            )
        ).scalar_one()
        confirmed_cnt = db.execute(
            select(func.count(TransactionCategorization.id)).where(
                TransactionCategorization.user_id == user.id,
                TransactionCategorization.review_status.in_(["confirmed", "overridden"]),
            )
        ).scalar_one()
        items = [self._serialize_tx_categorization(rec, tx, merch) for rec, tx, merch in rows]
        return TransactionCategorizationListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            needs_review_count=needs_review_cnt,
            confirmed_count=confirmed_cnt,
        )

    def override_transaction_categorization(
        self,
        db: Session,
        user: User,
        transaction_id: uuid.UUID,
        req: TransactionCategorizationOverrideRequest,
    ) -> TransactionCategorizationResponse:
        tx = self.repo.get_transaction_by_id(db, user.id, transaction_id)
        if tx is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

        new_cat = self.repo.get_category_by_id(db, user.id, req.category_id)
        if new_cat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")

        if tx.transaction_type in ("income", "expense") and new_cat.category_type != tx.transaction_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{new_cat.name}' ({new_cat.category_type}) does not match transaction type '{tx.transaction_type}'.",
            )

        rec = self.repo.get_categorization_by_tx(db, user.id, transaction_id)
        if rec is None:
            # Ensure record exists by creating one cleanly
            categories = self.repo.list_available_categories(db, user.id)
            cat_by_name = {c.name.lower(): c for c in categories}
            from app.services.ai.merchant_intelligence import resolve_or_upsert_merchant

            merchant_obj, _ = resolve_or_upsert_merchant(
                db,
                self.repo,
                user.id,
                description=tx.description,
                merchant_payee=tx.merchant_payee,
                amount=tx.amount,
                tx_type=tx.transaction_type,
                categories_by_name=cat_by_name,
            )
            rec = TransactionCategorization(
                user_id=user.id,
                transaction_id=tx.id,
                merchant_id=merchant_obj.id,
                classification_method="user_override",
                confidence=Decimal("1.0000"),
            )

        prev_cat_id = tx.category_id
        prev_cat_name = tx.category.name if tx.category else None
        merchant = (
            self.repo.get_merchant_by_id(db, user.id, rec.merchant_id)
            if rec.merchant_id
            else None
        )
        prev_merch_name = merchant.normalized_name if merchant else None

        if req.action != "dismiss":
            tx.category_id = new_cat.id
            db.add(tx)
            rec.current_category_id = new_cat.id
            rec.current_category_name = new_cat.name
            rec.suggested_category_id = new_cat.id
            rec.suggested_category_name = new_cat.name
            rec.predicted_category_name = new_cat.name
            rec.classification_method = "user_override" if req.action == "override" else "user_confirmed"
            rec.confidence = Decimal("1.0000")
            rec.review_status = "overridden" if req.action == "override" else "confirmed"
            rec.explanation = (
                f"Confirmed by user as '{new_cat.name}'."
                if req.action == "confirm"
                else f"Overridden by user from '{prev_cat_name or 'Uncategorized'}' to '{new_cat.name}'."
            )
        else:
            rec.review_status = "dismissed"

        rec.updated_at = dt.datetime.now(dt.UTC)
        db.add(rec)

        new_merch_name = prev_merch_name
        if merchant is not None:
            if req.normalized_merchant_name:
                merchant.normalized_name = req.normalized_merchant_name.strip()[:150]
                merchant.is_user_confirmed = True
                new_merch_name = merchant.normalized_name
            if req.save_merchant_mapping and req.action != "dismiss":
                merchant.default_category_id = new_cat.id
                merchant.default_category_name = new_cat.name
                merchant.is_user_confirmed = True
                mapping = self.repo.get_merchant_category_mapping(db, user.id, merchant.id)
                if mapping is None:
                    mapping = MerchantCategoryMapping(
                        user_id=user.id,
                        merchant_id=merchant.id,
                        category_id=new_cat.id,
                        category_name=new_cat.name,
                    )
                mapping.category_id = new_cat.id
                mapping.category_name = new_cat.name
                mapping.source = "user_override"
                mapping.confidence = Decimal("1.0000")
                mapping.is_authoritative = True
                mapping.updated_at = dt.datetime.now(dt.UTC)
                db.add(mapping)
            db.add(merchant)

        feedback = CategorizationFeedback(
            user_id=user.id,
            transaction_id=tx.id,
            categorization_id=rec.id,
            action=req.action,
            previous_category_id=prev_cat_id,
            previous_category_name=prev_cat_name,
            new_category_id=new_cat.id if req.action != "dismiss" else prev_cat_id,
            new_category_name=new_cat.name if req.action != "dismiss" else prev_cat_name,
            previous_merchant_name=prev_merch_name,
            new_merchant_name=new_merch_name,
            notes=req.notes,
        )
        db.add(feedback)
        db.commit()
        db.refresh(rec)
        db.refresh(tx)
        if merchant is not None:
            db.refresh(merchant)
        return self._serialize_tx_categorization(rec, tx, merchant)

    def list_feedback(self, db: Session, user: User) -> list[CategorizationFeedbackResponse]:
        return [
            CategorizationFeedbackResponse.model_validate(f)
            for f in self.repo.list_feedback(db, user.id, limit=50)
        ]

    # ── Merchants ──────────────────────────────────────────────────────────────

    def list_merchants(
        self,
        db: Session,
        user: User,
        *,
        search: str | None = None,
        confirmed_only: bool = False,
        page: int = 1,
        page_size: int = 25,
    ) -> MerchantListResponse:
        merchants, total = self.repo.list_merchants(
            db, user.id, search=search, confirmed_only=confirmed_only, page=page, page_size=page_size
        )
        items = [MerchantIdentityResponse.model_validate(m, from_attributes=True) for m in merchants]
        return MerchantListResponse(items=items, total=total, page=page, page_size=page_size)

    def update_merchant(
        self,
        db: Session,
        user: User,
        merchant_id: uuid.UUID,
        req: MerchantUpdateRequest,
    ) -> MerchantIdentityResponse:
        merchant = self.repo.get_merchant_by_id(db, user.id, merchant_id)
        if merchant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Merchant not found.")

        if req.normalized_name:
            merchant.normalized_name = req.normalized_name.strip()[:150]
            merchant.is_user_confirmed = True

        if req.is_user_confirmed is not None:
            merchant.is_user_confirmed = req.is_user_confirmed

        if req.default_category_id is not None:
            cat = self.repo.get_category_by_id(db, user.id, req.default_category_id)
            if cat is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found.")
            merchant.default_category_id = cat.id
            merchant.default_category_name = cat.name
            merchant.is_user_confirmed = True

            mapping = self.repo.get_merchant_category_mapping(db, user.id, merchant.id)
            if mapping is None:
                mapping = MerchantCategoryMapping(
                    user_id=user.id,
                    merchant_id=merchant.id,
                    category_id=cat.id,
                    category_name=cat.name,
                )
            mapping.category_id = cat.id
            mapping.category_name = cat.name
            mapping.source = "user_override"
            mapping.confidence = Decimal("1.0000")
            mapping.is_authoritative = True
            mapping.updated_at = dt.datetime.now(dt.UTC)
            db.add(mapping)

            if req.apply_to_existing_transactions:
                linked_cats = db.execute(
                    select(TransactionCategorization).where(
                        TransactionCategorization.user_id == user.id,
                        TransactionCategorization.merchant_id == merchant.id,
                        TransactionCategorization.review_status.in_(["needs_review", "auto_categorized"]),
                    )
                ).scalars().all()
                for c_rec in linked_cats:
                    c_rec.suggested_category_id = cat.id
                    c_rec.suggested_category_name = cat.name
                    c_rec.predicted_category_name = cat.name
                    c_rec.classification_method = "confirmed_mapping"
                    c_rec.confidence = Decimal("0.9800")
                    c_rec.explanation = f"Updated via merchant mapping for '{merchant.normalized_name}'."
                    db.add(c_rec)

        merchant.updated_at = dt.datetime.now(dt.UTC)
        db.add(merchant)
        db.commit()
        db.refresh(merchant)
        merchant = self.repo.get_merchant_by_id(db, user.id, merchant.id) or merchant
        return MerchantIdentityResponse.model_validate(merchant, from_attributes=True)

    # ── Recurring Candidates ───────────────────────────────────────────────────

    def list_recurring_candidates(
        self, db: Session, user: User, *, review_status: str | None = None
    ) -> RecurringCandidateListResponse:
        items = self.repo.list_recurring_candidates(db, user.id, review_status=review_status)
        all_items = self.repo.list_recurring_candidates(db, user.id) if review_status else items
        pending_cnt = sum(1 for i in all_items if i.review_status == "pending")
        confirmed_cnt = sum(1 for i in all_items if i.review_status in ("confirmed", "linked"))
        return RecurringCandidateListResponse(
            items=[RecurringPaymentCandidateResponse.model_validate(i) for i in items],
            total=len(items),
            pending_count=pending_cnt,
            confirmed_count=confirmed_cnt,
        )

    def decide_recurring_candidate(
        self,
        db: Session,
        user: User,
        candidate_id: uuid.UUID,
        req: RecurringCandidateDecisionRequest,
    ) -> RecurringPaymentCandidateResponse:
        cand = self.repo.get_recurring_candidate_by_id(db, user.id, candidate_id)
        if cand is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recurring payment candidate not found.",
            )

        if req.decision == "reject":
            cand.review_status = "rejected"
        elif req.decision == "link_subscription" or (req.decision == "confirm" and (req.create_subscription or req.subscription_id)):
            target_sub: Subscription | None = None
            if req.subscription_id:
                target_sub = db.execute(
                    select(Subscription).where(
                        Subscription.id == req.subscription_id,
                        Subscription.user_id == user.id,
                    )
                ).scalar_one_or_none()
                if target_sub is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Target subscription not found.",
                    )
            elif req.create_subscription:
                cats = self.repo.list_available_categories(db, user.id)
                cat_match = next(
                    (
                        c
                        for c in cats
                        if cand.suggested_category_name
                        and c.name.lower() == cand.suggested_category_name.lower()
                    ),
                    None,
                )
                sub_category = "ott_streaming" if (cand.suggested_category_name or "").lower() == "subscriptions" else "other"
                anchor = (cand.last_seen_date or dt.date.today()).day
                target_sub = Subscription(
                    user_id=user.id,
                    financial_category_id=cat_match.id if cat_match else None,
                    subscription_name=cand.merchant_name,
                    provider_name=cand.merchant_name,
                    category=sub_category,
                    amount=cand.estimated_amount,
                    currency="INR",
                    billing_frequency=cand.frequency if cand.frequency in ("weekly", "monthly", "quarterly", "half_yearly", "yearly") else "monthly",
                    anchor_day=anchor,
                    start_date=cand.first_seen_date or dt.date.today(),
                    next_renewal_date=cand.next_expected_date,
                    previous_renewal_date=cand.last_seen_date,
                    status="active",
                    notes="Created from Phase 8 Recurring Payment Intelligence confirmation.",
                )
                db.add(target_sub)
                db.flush()

            if target_sub is not None:
                cand.linked_subscription_id = target_sub.id
                cand.review_status = "linked"
            else:
                cand.review_status = "confirmed"
        else:
            cand.review_status = "confirmed"

        cand.updated_at = dt.datetime.now(dt.UTC)
        db.add(cand)
        db.commit()
        db.refresh(cand)
        return RecurringPaymentCandidateResponse.model_validate(cand)

    # ── Spending Patterns, Anomalies, Insights ─────────────────────────────────

    def get_spending_patterns(
        self,
        db: Session,
        user: User,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> SpendingPatternsResponse:
        return compute_spending_patterns(
            db, self.repo, user.id, date_from=date_from, date_to=date_to
        )

    def list_anomalies(
        self,
        db: Session,
        user: User,
        *,
        review_status: str | None = None,
        severity: str | None = None,
    ) -> SpendingAnomalyListResponse:
        items = self.repo.list_anomalies(db, user.id, review_status=review_status, severity=severity)
        all_items = self.repo.list_anomalies(db, user.id) if (review_status or severity) else items
        open_cnt = sum(1 for a in all_items if a.review_status == "open")
        ack_cnt = sum(1 for a in all_items if a.review_status == "acknowledged")
        dis_cnt = sum(1 for a in all_items if a.review_status == "dismissed")
        return SpendingAnomalyListResponse(
            items=[SpendingAnomalyResponse.model_validate(a) for a in items],
            total=len(items),
            open_count=open_cnt,
            acknowledged_count=ack_cnt,
            dismissed_count=dis_cnt,
        )

    def review_anomaly(
        self, db: Session, user: User, anomaly_id: uuid.UUID, req: AnomalyReviewRequest
    ) -> SpendingAnomalyResponse:
        anom = self.repo.get_anomaly_by_id(db, user.id, anomaly_id)
        if anom is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anomaly not found.")
        status_map = {
            "acknowledge": "acknowledged",
            "dismiss": "dismissed",
            "reopen": "open",
        }
        anom.review_status = status_map[req.action]
        anom.reviewed_at = None if req.action == "reopen" else dt.datetime.now(dt.UTC)
        db.add(anom)
        db.commit()
        db.refresh(anom)
        return SpendingAnomalyResponse.model_validate(anom)

    def list_insights(
        self, db: Session, user: User, *, status_filter: str | None = None
    ) -> FinancialInsightListResponse:
        items = self.repo.list_insights(db, user.id, status_filter=status_filter)
        all_items = self.repo.list_insights(db, user.id) if status_filter else items
        new_cnt = sum(1 for i in all_items if i.status == "new")
        read_cnt = sum(1 for i in all_items if i.status == "read")
        dis_cnt = sum(1 for i in all_items if i.status == "dismissed")
        return FinancialInsightListResponse(
            items=[FinancialInsightResponse.model_validate(i) for i in items],
            total=len(items),
            new_count=new_cnt,
            read_count=read_cnt,
            dismissed_count=dis_cnt,
        )

    def review_insight(
        self, db: Session, user: User, insight_id: uuid.UUID, req: InsightReviewRequest
    ) -> FinancialInsightResponse:
        ins = self.repo.get_insight_by_id(db, user.id, insight_id)
        if ins is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found.")
        now = dt.datetime.now(dt.UTC)
        if req.action == "mark_read":
            ins.status = "read"
            ins.read_at = now
        elif req.action == "dismiss":
            ins.status = "dismissed"
            ins.dismissed_at = now
        else:
            ins.status = "new"
            ins.read_at = None
            ins.dismissed_at = None
        db.add(ins)
        db.commit()
        db.refresh(ins)
        return FinancialInsightResponse.model_validate(ins)

    def list_jobs(self, db: Session, user: User) -> list[AiProcessingJobResponse]:
        return [
            AiProcessingJobResponse.model_validate(j)
            for j in self.repo.list_jobs(db, user.id, limit=20)
        ]
