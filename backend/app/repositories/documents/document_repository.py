import datetime as dt
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.documents import (
    DocumentExtraction,
    DocumentLink,
    DocumentProcessingJob,
    DocumentReviewEvent,
    FinancialDocument,
)


class DocumentRepository:
    def create(self, db: Session, doc: FinancialDocument) -> FinancialDocument:
        db.add(doc)
        db.flush()
        return doc

    def get_by_id(
        self, db: Session, doc_id: uuid.UUID, user_id: uuid.UUID
    ) -> FinancialDocument | None:
        stmt = (
            select(FinancialDocument)
            .where(FinancialDocument.id == doc_id, FinancialDocument.user_id == user_id)
            .options(
                selectinload(FinancialDocument.extraction),
                selectinload(FinancialDocument.jobs),
                selectinload(FinancialDocument.review_events),
                selectinload(FinancialDocument.links),
            )
        )
        return db.execute(stmt).scalar_one_or_none()

    def get_by_hash(
        self, db: Session, user_id: uuid.UUID, file_hash: str
    ) -> FinancialDocument | None:
        stmt = (
            select(FinancialDocument)
            .where(FinancialDocument.user_id == user_id, FinancialDocument.file_hash == file_hash)
            .order_by(FinancialDocument.uploaded_at.asc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def list_documents(
        self,
        db: Session,
        user_id: uuid.UUID,
        *,
        category: str | None = None,
        status_filter: str | None = None,
        ocr_status: str | None = None,
        source: str | None = None,
        search: str | None = None,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        linked_target_type: str | None = None,
        linked_target_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FinancialDocument], int]:
        filters = [FinancialDocument.user_id == user_id]
        if category:
            filters.append(FinancialDocument.document_category == category)
        if status_filter:
            filters.append(FinancialDocument.processing_status == status_filter)
        if ocr_status:
            filters.append(FinancialDocument.ocr_status == ocr_status)
        if source:
            filters.append(FinancialDocument.source == source)
        if date_from:
            filters.append(
                FinancialDocument.uploaded_at
                >= dt.datetime.combine(date_from, dt.time.min, tzinfo=dt.UTC)
            )
        if date_to:
            filters.append(
                FinancialDocument.uploaded_at
                <= dt.datetime.combine(date_to, dt.time.max, tzinfo=dt.UTC)
            )

        base = (
            select(FinancialDocument)
            .where(*filters)
            .outerjoin(DocumentExtraction, DocumentExtraction.document_id == FinancialDocument.id)
        )

        if search and search.strip():
            term = f"%{search.strip()}%"
            base = base.where(
                or_(
                    FinancialDocument.original_filename.ilike(term),
                    DocumentExtraction.merchant_name.ilike(term),
                    DocumentExtraction.invoice_number.ilike(term),
                    DocumentExtraction.gstin.ilike(term),
                )
            )

        if linked_target_type or linked_target_id:
            link_sub = select(DocumentLink.document_id).where(DocumentLink.user_id == user_id)
            if linked_target_type:
                link_sub = link_sub.where(DocumentLink.target_type == linked_target_type)
            if linked_target_id:
                link_sub = link_sub.where(
                    or_(
                        DocumentLink.bill_id == linked_target_id,
                        DocumentLink.transaction_id == linked_target_id,
                        DocumentLink.subscription_id == linked_target_id,
                        DocumentLink.loan_id == linked_target_id,
                    )
                )
            base = base.where(FinancialDocument.id.in_(link_sub))

        total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()

        stmt = (
            base.options(
                selectinload(FinancialDocument.extraction),
                selectinload(FinancialDocument.links),
            )
            .order_by(FinancialDocument.uploaded_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(db.execute(stmt).scalars().unique().all())
        return items, total

    def get_overview_counts(self, db: Session, user_id: uuid.UUID) -> dict[str, int]:
        rows = db.execute(
            select(FinancialDocument.processing_status, func.count(FinancialDocument.id))
            .where(FinancialDocument.user_id == user_id)
            .group_by(FinancialDocument.processing_status)
        ).all()
        counts = {status_val: cnt for status_val, cnt in rows}
        total = sum(counts.values())
        return {
            "total_documents": total,
            "processed_count": (
                counts.get("extracted", 0)
                + counts.get("needs_review", 0)
                + counts.get("confirmed", 0)
            ),
            "needs_review_count": counts.get("needs_review", 0) + counts.get("extracted", 0),
            "processing_count": (
                counts.get("uploaded", 0)
                + counts.get("queued", 0)
                + counts.get("processing", 0)
            ),
            "failed_count": counts.get("failed", 0),
            "confirmed_count": counts.get("confirmed", 0),
            "rejected_count": counts.get("rejected", 0),
        }

    def list_recent(
        self, db: Session, user_id: uuid.UUID, limit: int = 5
    ) -> list[FinancialDocument]:
        stmt = (
            select(FinancialDocument)
            .where(FinancialDocument.user_id == user_id)
            .options(
                selectinload(FinancialDocument.extraction),
                selectinload(FinancialDocument.links),
            )
            .order_by(FinancialDocument.uploaded_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def get_active_job(
        self, db: Session, document_id: uuid.UUID, job_type: str = "ocr_extract"
    ) -> DocumentProcessingJob | None:
        stmt = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.document_id == document_id,
                DocumentProcessingJob.job_type == job_type,
                DocumentProcessingJob.status.in_(["queued", "processing"]),
            )
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def create_job(self, db: Session, job: DocumentProcessingJob) -> DocumentProcessingJob:
        db.add(job)
        db.flush()
        return job

    def claim_due_jobs(
        self, db: Session, *, worker_id: str, limit: int = 2
    ) -> list[DocumentProcessingJob]:
        now = dt.datetime.now(dt.UTC)
        # Recover jobs stuck in 'processing' for >10 minutes (worker crash recovery)
        stale_cutoff = now - dt.timedelta(minutes=10)
        stale = db.execute(
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.status == "processing",
                DocumentProcessingJob.started_at < stale_cutoff,
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for s_job in stale:
            if s_job.attempt_count < s_job.max_attempts:
                s_job.status = "queued"
                s_job.next_retry_at = now
                db.add(s_job)
            else:
                s_job.status = "failed"
                s_job.error_message = "Worker timeout recovery exceeded max attempts."
                s_job.completed_at = now
                db.add(s_job)

        stmt = (
            select(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.status == "queued",
                or_(
                    DocumentProcessingJob.next_retry_at.is_(None),
                    DocumentProcessingJob.next_retry_at <= now,
                ),
            )
            .order_by(DocumentProcessingJob.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = list(db.execute(stmt).scalars().all())
        for job in jobs:
            job.status = "processing"
            job.attempt_count += 1
            job.started_at = now
            job.worker_id = worker_id
            db.add(job)
        db.flush()
        return jobs

    def list_jobs(
        self, db: Session, user_id: uuid.UUID, limit: int = 50
    ) -> list[tuple[DocumentProcessingJob, str]]:
        stmt = (
            select(DocumentProcessingJob, FinancialDocument.original_filename)
            .join(FinancialDocument, FinancialDocument.id == DocumentProcessingJob.document_id)
            .where(DocumentProcessingJob.user_id == user_id)
            .order_by(DocumentProcessingJob.created_at.desc())
            .limit(limit)
        )
        return list(db.execute(stmt).all())

    def get_extraction(
        self, db: Session, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> DocumentExtraction | None:
        stmt = select(DocumentExtraction).where(
            DocumentExtraction.document_id == document_id,
            DocumentExtraction.user_id == user_id,
        )
        return db.execute(stmt).scalar_one_or_none()

    def add_review_event(self, db: Session, evt: DocumentReviewEvent) -> DocumentReviewEvent:
        db.add(evt)
        db.flush()
        return evt

    def get_link(
        self,
        db: Session,
        document_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
    ) -> DocumentLink | None:
        cond = DocumentLink.document_id == document_id
        if target_type == "bill":
            target_cond = DocumentLink.bill_id == target_id
        elif target_type == "transaction":
            target_cond = DocumentLink.transaction_id == target_id
        elif target_type == "subscription":
            target_cond = DocumentLink.subscription_id == target_id
        else:
            target_cond = DocumentLink.loan_id == target_id
        return db.execute(select(DocumentLink).where(cond, target_cond)).scalar_one_or_none()

    def find_created_link(
        self, db: Session, document_id: uuid.UUID, target_type: str
    ) -> DocumentLink | None:
        return db.execute(
            select(DocumentLink).where(
                DocumentLink.document_id == document_id,
                DocumentLink.target_type == target_type,
                DocumentLink.link_role == "created_from_document",
            )
        ).scalar_one_or_none()
