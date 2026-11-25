import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import and_, exists, func, not_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.finance import (
    FinancialAccount,
    FinancialCategory,
    FinancialTransaction,
    LedgerJournal,
)
from app.models.intelligence import (
    AiModelMetadata,
    AiProcessingJob,
    CategorizationFeedback,
    FinancialInsight,
    MerchantAlias,
    MerchantCategoryMapping,
    MerchantIdentity,
    RecurringPaymentCandidate,
    SpendingAnomaly,
    TransactionCategorization,
)


class IntelligenceRepository:
    """PostgreSQL repository for Phase 8 AI Expense Intelligence."""

    @staticmethod
    def _active_journal_clause():
        has_reversed = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(True),
            )
        )
        has_active = exists(
            select(LedgerJournal.id).where(
                LedgerJournal.transaction_id == FinancialTransaction.id,
                LedgerJournal.is_reversed.is_(False),
            )
        )
        return not_(and_(has_reversed, not_(has_active)))

    def list_eligible_transactions(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        tx_ids: list[uuid.UUID] | None = None,
        include_transfers: bool = False,
    ) -> list[FinancialTransaction]:
        stmt = (
            select(FinancialTransaction)
            .join(FinancialAccount, FinancialTransaction.account_id == FinancialAccount.id)
            .options(selectinload(FinancialTransaction.category))
            .where(
                FinancialTransaction.user_id == user_id,
                FinancialAccount.status != "disconnected",
                self._active_journal_clause(),
            )
            .order_by(FinancialTransaction.transaction_date.desc(), FinancialTransaction.created_at.desc())
        )
        if not include_transfers:
            stmt = stmt.where(
                FinancialTransaction.transfer_id.is_(None),
                FinancialTransaction.transaction_type.in_(["income", "expense"]),
            )
        if date_from:
            stmt = stmt.where(FinancialTransaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(FinancialTransaction.transaction_date <= date_to)
        if tx_ids:
            stmt = stmt.where(FinancialTransaction.id.in_(tx_ids))
        return list(db.execute(stmt).scalars().all())

    def get_transaction_by_id(
        self, db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> FinancialTransaction | None:
        stmt = (
            select(FinancialTransaction)
            .options(selectinload(FinancialTransaction.category))
            .where(
                FinancialTransaction.id == transaction_id,
                FinancialTransaction.user_id == user_id,
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_available_categories(
        self, db: Session, user_id: uuid.UUID
    ) -> list[FinancialCategory]:
        stmt = (
            select(FinancialCategory)
            .where(
                or_(
                    FinancialCategory.user_id.is_(None),
                    FinancialCategory.user_id == user_id,
                )
            )
            .order_by(FinancialCategory.category_type.asc(), FinancialCategory.name.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def get_category_by_id(
        self, db: Session, user_id: uuid.UUID, category_id: uuid.UUID
    ) -> FinancialCategory | None:
        stmt = select(FinancialCategory).where(
            FinancialCategory.id == category_id,
            or_(FinancialCategory.user_id.is_(None), FinancialCategory.user_id == user_id),
        )
        return db.execute(stmt).scalar_one_or_none()

    # ── Merchants & Mappings ───────────────────────────────────────────────────

    def get_merchant_by_key(
        self, db: Session, user_id: uuid.UUID, canonical_key: str
    ) -> MerchantIdentity | None:
        stmt = select(MerchantIdentity).where(
            MerchantIdentity.user_id == user_id,
            MerchantIdentity.canonical_key == canonical_key,
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_merchant_by_id(
        self, db: Session, user_id: uuid.UUID, merchant_id: uuid.UUID
    ) -> MerchantIdentity | None:
        stmt = (
            select(MerchantIdentity)
            .options(selectinload(MerchantIdentity.aliases), selectinload(MerchantIdentity.category_mapping))
            .where(MerchantIdentity.id == merchant_id, MerchantIdentity.user_id == user_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_alias_by_pattern(
        self, db: Session, user_id: uuid.UUID, raw_pattern: str
    ) -> MerchantAlias | None:
        stmt = select(MerchantAlias).where(
            MerchantAlias.user_id == user_id,
            MerchantAlias.raw_pattern == raw_pattern,
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_merchant_category_mapping(
        self, db: Session, user_id: uuid.UUID, merchant_id: uuid.UUID
    ) -> MerchantCategoryMapping | None:
        stmt = select(MerchantCategoryMapping).where(
            MerchantCategoryMapping.user_id == user_id,
            MerchantCategoryMapping.merchant_id == merchant_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_merchants(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        search: str | None = None,
        confirmed_only: bool = False,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[MerchantIdentity], int]:
        filters = [MerchantIdentity.user_id == user_id]
        if confirmed_only:
            filters.append(MerchantIdentity.is_user_confirmed.is_(True))
        if search:
            q = f"%{search.strip()}%"
            filters.append(
                or_(
                    MerchantIdentity.normalized_name.ilike(q),
                    MerchantIdentity.canonical_key.ilike(q),
                    MerchantIdentity.default_category_name.ilike(q),
                )
            )
        total = db.execute(select(func.count(MerchantIdentity.id)).where(*filters)).scalar_one()
        stmt = (
            select(MerchantIdentity)
            .options(selectinload(MerchantIdentity.aliases))
            .where(*filters)
            .order_by(MerchantIdentity.total_spent.desc(), MerchantIdentity.transaction_count.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(db.execute(stmt).scalars().all()), total

    # ── Categorizations & Feedback ─────────────────────────────────────────────

    def get_categorization_by_tx(
        self, db: Session, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> TransactionCategorization | None:
        stmt = select(TransactionCategorization).where(
            TransactionCategorization.user_id == user_id,
            TransactionCategorization.transaction_id == transaction_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_categorizations(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        review_status: str | None = None,
        method: str | None = None,
        search: str | None = None,
        min_confidence: float | None = None,
        max_confidence: float | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[tuple[TransactionCategorization, FinancialTransaction, MerchantIdentity | None]], int]:
        stmt = (
            select(TransactionCategorization, FinancialTransaction, MerchantIdentity)
            .join(
                FinancialTransaction,
                TransactionCategorization.transaction_id == FinancialTransaction.id,
            )
            .outerjoin(
                MerchantIdentity,
                TransactionCategorization.merchant_id == MerchantIdentity.id,
            )
            .where(TransactionCategorization.user_id == user_id)
        )
        count_stmt = (
            select(func.count(TransactionCategorization.id))
            .select_from(TransactionCategorization)
            .join(
                FinancialTransaction,
                TransactionCategorization.transaction_id == FinancialTransaction.id,
            )
            .where(TransactionCategorization.user_id == user_id)
        )
        filters = []
        if review_status:
            filters.append(TransactionCategorization.review_status == review_status)
        if method:
            filters.append(TransactionCategorization.classification_method == method)
        if min_confidence is not None:
            filters.append(TransactionCategorization.confidence >= Decimal(str(min_confidence)))
        if max_confidence is not None:
            filters.append(TransactionCategorization.confidence <= Decimal(str(max_confidence)))
        if search:
            q = f"%{search.strip()}%"
            filters.append(
                or_(
                    FinancialTransaction.description.ilike(q),
                    FinancialTransaction.merchant_payee.ilike(q),
                    TransactionCategorization.suggested_category_name.ilike(q),
                    TransactionCategorization.current_category_name.ilike(q),
                )
            )
        if filters:
            stmt = stmt.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = db.execute(count_stmt).scalar_one()
        stmt = (
            stmt.order_by(FinancialTransaction.transaction_date.desc(), TransactionCategorization.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(r[0], r[1], r[2]) for r in db.execute(stmt).all()]
        return rows, total

    def list_feedback(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 50
    ) -> list[CategorizationFeedback]:
        stmt = (
            select(CategorizationFeedback)
            .where(CategorizationFeedback.user_id == user_id)
            .order_by(CategorizationFeedback.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_model_metadata(self, db: Session, user_id: uuid.UUID) -> AiModelMetadata | None:
        stmt = select(AiModelMetadata).where(AiModelMetadata.user_id == user_id)
        return db.execute(stmt).scalar_one_or_none()

    # ── Recurring Candidates ───────────────────────────────────────────────────

    def list_recurring_candidates(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        review_status: str | None = None,
    ) -> list[RecurringPaymentCandidate]:
        stmt = select(RecurringPaymentCandidate).where(RecurringPaymentCandidate.user_id == user_id)
        if review_status:
            stmt = stmt.where(RecurringPaymentCandidate.review_status == review_status)
        stmt = stmt.order_by(
            RecurringPaymentCandidate.confidence.desc(),
            RecurringPaymentCandidate.estimated_amount.desc(),
        )
        return list(db.execute(stmt).scalars().all())

    def get_recurring_candidate_by_id(
        self, db: Session, user_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> RecurringPaymentCandidate | None:
        stmt = select(RecurringPaymentCandidate).where(
            RecurringPaymentCandidate.id == candidate_id,
            RecurringPaymentCandidate.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    # ── Anomalies & Insights ───────────────────────────────────────────────────

    def list_anomalies(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        review_status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[SpendingAnomaly]:
        stmt = select(SpendingAnomaly).where(SpendingAnomaly.user_id == user_id)
        if review_status:
            stmt = stmt.where(SpendingAnomaly.review_status == review_status)
        if severity:
            stmt = stmt.where(SpendingAnomaly.severity == severity)
        stmt = stmt.order_by(SpendingAnomaly.detected_at.desc(), SpendingAnomaly.deviation_pct.desc()).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def get_anomaly_by_id(
        self, db: Session, user_id: uuid.UUID, anomaly_id: uuid.UUID
    ) -> SpendingAnomaly | None:
        stmt = select(SpendingAnomaly).where(
            SpendingAnomaly.id == anomaly_id,
            SpendingAnomaly.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_insights(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        limit: int = 50,
    ) -> list[FinancialInsight]:
        stmt = select(FinancialInsight).where(FinancialInsight.user_id == user_id)
        if status_filter:
            stmt = stmt.where(FinancialInsight.status == status_filter)
        stmt = stmt.order_by(FinancialInsight.generated_at.desc()).limit(limit)
        return list(db.execute(stmt).scalars().all())

    def get_insight_by_id(
        self, db: Session, user_id: uuid.UUID, insight_id: uuid.UUID
    ) -> FinancialInsight | None:
        stmt = select(FinancialInsight).where(
            FinancialInsight.id == insight_id,
            FinancialInsight.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    # ── Jobs & Claiming ────────────────────────────────────────────────────────

    def get_active_job(
        self, db: Session, user_id: uuid.UUID, job_type: str = "full_intelligence"
    ) -> AiProcessingJob | None:
        stmt = (
            select(AiProcessingJob)
            .where(
                AiProcessingJob.user_id == user_id,
                AiProcessingJob.job_type == job_type,
                AiProcessingJob.status.in_(["queued", "processing"]),
            )
            .order_by(AiProcessingJob.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_jobs(
        self, db: Session, user_id: uuid.UUID, *, limit: int = 20
    ) -> list[AiProcessingJob]:
        stmt = (
            select(AiProcessingJob)
            .where(AiProcessingJob.user_id == user_id)
            .order_by(AiProcessingJob.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def claim_next_queued_job(self, db: Session) -> AiProcessingJob | None:
        stmt = (
            select(AiProcessingJob)
            .where(AiProcessingJob.status == "queued")
            .order_by(AiProcessingJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = db.execute(stmt).scalar_one_or_none()
        if job is None:
            return None
        job.status = "processing"
        job.attempt_count += 1
        job.started_at = dt.datetime.now(dt.UTC)
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
